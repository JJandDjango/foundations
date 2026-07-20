"""Structural parser for prompt files (SPEC §1).

Deterministic validation of:

- YAML frontmatter presence and required fields (SPEC §1.1).
- XML tag extraction + nesting detection + open/close balance (SPEC §1.2).
- ``reference: true`` gated by the matched ``FileRule.allow_reference``
  (SPEC §1.3). A file can only opt out of full validation if a rule
  matches AND permits it. Default-deny.
- Token counting via :mod:`tiktoken` (required — no heuristic fallback,
  SPEC §3).

Tag *order* is deliberately not validated (SPEC §1.2) — order is
editorial, not behavioral.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tiktoken
import yaml

from prompt_lang.config import Config, FileRule, load_config
from prompt_lang.errors import ValidationResult


FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
OPEN_TAG_PATTERN = re.compile(r"<([a-z][a-z0-9-]*)>", re.IGNORECASE)
CLOSE_TAG_PATTERN = re.compile(r"</([a-z][a-z0-9-]*)>", re.IGNORECASE)
TAG_PAIR_PATTERN = re.compile(
    r"<([a-z][a-z0-9-]*)>(.*?)</\1>", re.DOTALL | re.IGNORECASE
)

# Built once per process, reused across parses.
_TIKTOKEN_ENCODING = tiktoken.get_encoding("cl100k_base")


@dataclass
class Tag:
    """A parsed XML tag pair."""

    name: str
    content: str
    start_line: int
    end_line: int


@dataclass
class ParsedPrompt:
    """Structured result of parsing a prompt file."""

    frontmatter: dict[str, Any] | None = None
    frontmatter_end_line: int = 0
    tags: list[Tag] = field(default_factory=list)
    raw_content: str = ""

    def get_tag(self, name: str) -> Tag | None:
        for tag in self.tags:
            if tag.name.lower() == name.lower():
                return tag
        return None

    def has_tag(self, name: str) -> bool:
        return self.get_tag(name) is not None


def parse_file(
    file_path: Path | str,
    config: Config | None = None,
    file_rule: FileRule | None = None,
) -> tuple[ParsedPrompt, ValidationResult]:
    """Parse a prompt file from disk. UTF-8 mandatory."""
    file_path = Path(file_path)
    result = ValidationResult(file_path=str(file_path))

    if config is None:
        config = load_config()

    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        result.add_error(0, f"Failed to read file: {exc}")
        return ParsedPrompt(), result

    return parse_content(content, result, config, file_rule)


def parse_content(
    content: str,
    result: ValidationResult,
    config: Config,
    file_rule: FileRule | None = None,
) -> tuple[ParsedPrompt, ValidationResult]:
    """Parse prompt content. Validates structure; does not validate
    semantics (ambiguous-language check lives in the validator)."""
    parsed = ParsedPrompt(raw_content=content)
    lines = content.split("\n")

    skip_frontmatter = file_rule is not None and file_rule.skip_frontmatter
    skip_required_tags = file_rule is not None and file_rule.skip_required_tags

    if skip_frontmatter:
        parsed.frontmatter = None
        parsed.frontmatter_end_line = 0
    else:
        parsed.frontmatter, parsed.frontmatter_end_line = _parse_frontmatter(
            content, result, config
        )

    # SPEC §1.3: reference-gating. reference: true only honored if the
    # matched FileRule sets allow_reference: true. Otherwise, reject and
    # stop — no point pushing an "unauthorized reference" file through the
    # rest of validation; the errors would be noise.
    if parsed.frontmatter and parsed.frontmatter.get("reference") is True:
        token_count = _count_tokens(content)
        result.token_count = token_count
        if file_rule is not None and file_rule.allow_reference:
            return parsed, result
        allowed_patterns = _allowed_reference_patterns(config)
        hint = (
            ", ".join(repr(p) for p in allowed_patterns)
            if allowed_patterns
            else "(no allow_reference rules configured)"
        )
        rule_desc = (
            f"pattern {file_rule.pattern!r}"
            if file_rule is not None
            else "no file_rule matches this path"
        )
        result.add_error(
            1,
            f"'reference: true' is not authorized ({rule_desc}). "
            f"Files using the reference flag must match a file_rule with "
            f"allow_reference: true. Authorized patterns: {hint}",
        )
        return parsed, result

    body_start = parsed.frontmatter_end_line
    body_content = "\n".join(lines[body_start:])
    parsed.tags = _extract_tags(body_content, body_start, lines, result, config)

    _check_nesting(lines, body_start, result, config)

    if not skip_required_tags:
        _check_required_tags(parsed, result, config)

    token_count = _count_tokens(content)
    result.token_count = token_count
    _check_token_limits(token_count, result, config)

    return parsed, result


def _parse_frontmatter(
    content: str,
    result: ValidationResult,
    config: Config,
) -> tuple[dict[str, Any] | None, int]:
    if not content.startswith("---"):
        result.add_error(1, "Missing YAML frontmatter (file must start with '---')")
        return None, 0

    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        result.add_error(1, "Malformed YAML frontmatter (missing closing '---')")
        return None, 0

    yaml_content = match.group(1)
    end_line = match.group(0).count("\n")

    try:
        frontmatter = yaml.safe_load(yaml_content)
    except yaml.YAMLError as exc:
        result.add_error(1, f"Invalid YAML in frontmatter: {exc}")
        return None, end_line

    if frontmatter is None:
        frontmatter = {}
    if not isinstance(frontmatter, dict):
        result.add_error(1, "Frontmatter must be a YAML mapping")
        return None, end_line

    for required in config.validation.frontmatter.required:
        if required not in frontmatter:
            result.add_error(
                1, f"Missing required frontmatter field: '{required}'"
            )

    return frontmatter, end_line


def _scan_tag_lines(
    all_lines: list[str], body_start_line: int
) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    """Collect open/close tag occurrences as name -> [line numbers]."""
    open_tags: dict[str, list[int]] = {}
    close_tags: dict[str, list[int]] = {}
    for i, line in enumerate(all_lines[body_start_line:], start=body_start_line + 1):
        for match in OPEN_TAG_PATTERN.finditer(line):
            open_tags.setdefault(match.group(1).lower(), []).append(i)
        for match in CLOSE_TAG_PATTERN.finditer(line):
            close_tags.setdefault(match.group(1).lower(), []).append(i)
    return open_tags, close_tags


def _report_tag_errors(
    open_tags: dict[str, list[int]],
    close_tags: dict[str, list[int]],
    recognized: set[str],
    result: ValidationResult,
) -> None:
    """Report unrecognized, unclosed, and extra-closing tag errors."""
    for tag_name in set(open_tags) | set(close_tags):
        if tag_name not in recognized:
            line_num = (open_tags.get(tag_name, [0]) + close_tags.get(tag_name, [0]))[0]
            result.add_error(line_num, f"Unrecognized tag: <{tag_name}>")

    for tag_name, open_lines in open_tags.items():
        close_lines = close_tags.get(tag_name, [])
        if len(open_lines) > len(close_lines):
            for line_num in open_lines[len(close_lines):]:
                result.add_error(line_num, f"Unclosed tag: <{tag_name}>")

    for tag_name, close_lines in close_tags.items():
        open_lines = open_tags.get(tag_name, [])
        if len(close_lines) > len(open_lines):
            for line_num in close_lines[len(open_lines):]:
                result.add_error(line_num, f"Extra closing tag: </{tag_name}>")


def _build_tag_pairs(body: str, body_start_line: int) -> list[Tag]:
    """Materialize Tag objects for every well-formed open/close pair."""
    tags: list[Tag] = []
    for match in TAG_PAIR_PATTERN.finditer(body):
        name = match.group(1).lower()
        content = match.group(2)
        start_line = body[: match.start()].count("\n") + body_start_line + 1
        end_line = body[: match.end()].count("\n") + body_start_line + 1
        tags.append(
            Tag(
                name=name,
                content=content.strip(),
                start_line=start_line,
                end_line=end_line,
            )
        )
    return tags


def _extract_tags(
    body: str,
    body_start_line: int,
    all_lines: list[str],
    result: ValidationResult,
    config: Config,
) -> list[Tag]:
    recognized = set(config.validation.all_tags)
    open_tags, close_tags = _scan_tag_lines(all_lines, body_start_line)
    _report_tag_errors(open_tags, close_tags, recognized, result)
    return _build_tag_pairs(body, body_start_line)


def _line_tag_events(line: str, recognized: set[str]) -> list[tuple[int, str, str]]:
    """Collect recognized open/close tag events on a line, in column order."""
    events: list[tuple[int, str, str]] = []
    for match in OPEN_TAG_PATTERN.finditer(line):
        name = match.group(1).lower()
        if name in recognized:
            events.append((match.start(), "open", name))
    for match in CLOSE_TAG_PATTERN.finditer(line):
        name = match.group(1).lower()
        if name in recognized:
            events.append((match.start(), "close", name))
    events.sort(key=lambda ev: ev[0])
    return events


def _apply_nesting_event(
    stack: list[tuple[str, int]],
    kind: str,
    name: str,
    line_num: int,
    result: ValidationResult,
) -> None:
    """Advance the nesting automaton one event; report nesting errors."""
    if kind == "open":
        if stack:
            parent, parent_line = stack[-1]
            result.add_error(
                line_num,
                f"Nested tag detected: <{name}> inside <{parent}> "
                f"(opened at line {parent_line})",
            )
        stack.append((name, line_num))
        return
    if stack and stack[-1][0] == name:
        stack.pop()
    elif stack:
        expected, _ = stack[-1]
        result.add_error(
            line_num,
            f"Mismatched closing tag: expected </{expected}>, "
            f"found </{name}>",
        )


def _check_nesting(
    all_lines: list[str],
    body_start_line: int,
    result: ValidationResult,
    config: Config,
) -> None:
    recognized = set(config.validation.all_tags)
    stack: list[tuple[str, int]] = []

    for i, line in enumerate(all_lines[body_start_line:], start=body_start_line + 1):
        for _, kind, name in _line_tag_events(line, recognized):
            _apply_nesting_event(stack, kind, name, i, result)


def _check_required_tags(
    parsed: ParsedPrompt,
    result: ValidationResult,
    config: Config,
) -> None:
    for required in config.validation.required_tags:
        if not parsed.has_tag(required):
            result.add_error(0, f"Missing required tag: <{required}>")


def _count_tokens(content: str) -> int:
    return len(_TIKTOKEN_ENCODING.encode(content))


def _check_token_limits(
    token_count: int,
    result: ValidationResult,
    config: Config,
) -> None:
    tokens = config.validation.tokens
    if token_count >= tokens.fail_at:
        result.add_error(
            0,
            f"Token count ({token_count}) exceeds fail threshold ({tokens.fail_at})",
        )
    elif token_count >= tokens.warn_at:
        result.add_warning(
            0,
            f"Token count ({token_count}) exceeds warn threshold ({tokens.warn_at})",
        )


def _allowed_reference_patterns(config: Config) -> list[str]:
    return [rule.pattern for rule in config.file_rules if rule.allow_reference]
