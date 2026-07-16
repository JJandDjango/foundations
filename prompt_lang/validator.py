"""End-to-end validator and CLI for prompt files (SPEC §6).

Orchestrates:

1. ``load_config`` → :class:`Config`
2. File-rule resolution (fnmatch against POSIX-normalized path; SPEC §5).
3. ``parse_file`` → :class:`ParsedPrompt` + :class:`ValidationResult`.
4. Ambiguous-language check against ``<instructions>`` content (SPEC §2.1).
5. File-rule tag requirements (required/forbidden tags; SPEC §5).
6. Directive block validation (if a ``<directives>`` tag is present; SPEC §4).
7. Instruction-step action-keyword enforcement (if configured; SPEC §2.2).

Cross-file / reference-integrity validation lives in a consumer's lint
layer, not here — prompt_lang sees one file at a time.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from prompt_lang._globs import glob_match
from prompt_lang.config import Config, FileRule, load_config
from prompt_lang.directives import (
    extract_instruction_steps,
    parse_directives,
    validate_directive,
    validate_instruction_step,
)
from prompt_lang.errors import ValidationResult
from prompt_lang.parser import ParsedPrompt, parse_file


EXIT_SUCCESS = 0
EXIT_VALIDATION_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_FILE_NOT_FOUND = 3


def match_file_rule(file_path: Path | str, config: Config) -> FileRule | None:
    """Return the first :class:`FileRule` whose pattern matches ``file_path``.

    Paths are normalized to POSIX form before matching (SPEC §5 — Windows
    portability):

    - Backslashes are converted to forward slashes so a Windows-authored
      path like ``.agentic\\agents\\dev.md`` matches a POSIX pattern
      ``**/.agentic/agents/*.md`` regardless of host platform. ``PurePath``
      alone is insufficient: ``PurePosixPath`` treats ``\\`` as a literal
      filename character.
    - A leading ``/`` is stripped so an absolute POSIX path
      (``/tmp/.../foo.md``) matches a pattern starting with ``**/``. The
      ``**/`` glob compiles to ``(?:[^/]+/)*`` which cannot consume a
      leading separator. Windows drive prefixes (``C:/...``) are left in
      place — they match as an ordinary path component.

    Matching is case-insensitive on Windows and case-sensitive on Unix
    (``compile_glob`` reads ``os.name``).
    """
    posix = str(file_path).replace("\\", "/")
    if posix.startswith("/"):
        posix = posix[1:]
    for rule in config.file_rules:
        if glob_match(rule.pattern, posix):
            return rule
    return None


def validate_file(file_path: Path, config: Config) -> ValidationResult:
    """Validate one prompt file and return its :class:`ValidationResult`."""
    rule = match_file_rule(file_path, config)
    parsed, result = parse_file(file_path, config, rule)

    # If reference-gating short-circuited (authorized), parsed has no tags;
    # skip the rest. Reference-denied produces an error and also has no tags.
    if parsed.frontmatter and parsed.frontmatter.get("reference") is True:
        return result

    if config.validation.semantic_check and not (rule and rule.skip_frontmatter):
        _check_ambiguous_language(parsed, result, config)

    _apply_file_rule_tags(parsed, result, rule)
    _validate_directives_block(parsed, result, config)
    _validate_instruction_actions(parsed, result, config)
    return result


def validate_directory(dir_path: Path, config: Config) -> list[ValidationResult]:
    """Validate every ``.md`` file under ``dir_path`` (recursive)."""
    return [validate_file(p, config) for p in sorted(dir_path.rglob("*.md"))]


# ---------------------------------------------------------------------------
# Internals.
# ---------------------------------------------------------------------------


def _check_ambiguous_language(
    parsed: ParsedPrompt,
    result: ValidationResult,
    config: Config,
) -> None:
    """Flag ambiguous-language patterns inside the ``<instructions>`` tag."""
    tag = parsed.get_tag("instructions")
    if tag is None:
        return
    patterns = config.validation.ambiguous_patterns
    if not patterns:
        return

    # Word-boundary match, case-insensitive. Multi-word patterns ("try to")
    # are treated as verbatim phrases.
    regexes = [
        (pat, re.compile(r"\b" + re.escape(pat) + r"\b", re.IGNORECASE))
        for pat in patterns
    ]
    # Line numbering within the tag body — the tag starts on start_line,
    # and the content is stripped; we walk the raw content lines.
    for offset, line in enumerate(tag.content.split("\n"), start=0):
        for pat, rx in regexes:
            if rx.search(line):
                result.add_error(
                    tag.start_line + offset + 1,
                    f"Ambiguous language in <instructions>: {pat!r}",
                )


def _apply_file_rule_tags(
    parsed: ParsedPrompt,
    result: ValidationResult,
    rule: FileRule | None,
) -> None:
    if rule is None:
        return
    for required in rule.required_tags:
        if not parsed.has_tag(required):
            result.add_error(
                0,
                f"File matching pattern {rule.pattern!r} requires <{required}> tag",
            )
    for forbidden in rule.forbidden_tags:
        if parsed.has_tag(forbidden):
            tag = parsed.get_tag(forbidden)
            line_num = tag.start_line if tag else 0
            result.add_error(
                line_num,
                f"File matching pattern {rule.pattern!r} forbids <{forbidden}> tag",
            )


def _validate_directives_block(
    parsed: ParsedPrompt,
    result: ValidationResult,
    config: Config,
) -> None:
    tag = parsed.get_tag("directives")
    if tag is None:
        return
    for directive in parse_directives(tag.content):
        ok, reason = validate_directive(directive.content, config.validation.directives)
        if not ok:
            result.add_error(
                tag.start_line + directive.line_number,
                f"Invalid directive: {reason}",
            )


def _validate_instruction_actions(
    parsed: ParsedPrompt,
    result: ValidationResult,
    config: Config,
) -> None:
    if not config.validation.instructions.enforce_actions:
        return
    tag = parsed.get_tag("instructions")
    if tag is None:
        return
    for step, rel_line in extract_instruction_steps(tag.content):
        ok, reason = validate_instruction_step(step, config.validation.instructions)
        if not ok:
            result.add_error(
                tag.start_line + rel_line,
                reason,
            )


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        config = load_config(args.config)
    except (OSError, ValueError) as exc:
        print(f"Error loading config: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    if args.no_semantic:
        config.validation.semantic_check = False

    target = Path(args.path)
    if not target.exists():
        print(f"Error: Path not found: {target}", file=sys.stderr)
        return EXIT_FILE_NOT_FOUND

    if target.is_file():
        results = [validate_file(target, config)]
    else:
        results = validate_directory(target, config)

    all_passed = _print_results(results, verbose=args.verbose)
    return EXIT_SUCCESS if all_passed else EXIT_VALIDATION_ERROR


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m prompt_lang",
        description="Validate prompt files against the Prompt Programming Language spec.",
        epilog=(
            "Exit codes: 0=success, 1=validation errors, "
            "2=config error, 3=file not found"
        ),
    )
    parser.add_argument(
        "path",
        help="Path to a prompt file (.md) or directory to validate",
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Path to config file (default: prompt-lang.config.yaml)",
    )
    parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="Skip semantic validation (ambiguous-language detection)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output (show passing files)",
    )
    return parser.parse_args(argv)


def _print_results(results: list[ValidationResult], verbose: bool = False) -> bool:
    passed = 0
    failed = 0
    for result in results:
        if result.passed:
            passed += 1
            if verbose:
                print(f"PASS: {result.file_path}")
        else:
            failed += 1
            _print_failure(result)
    total = passed + failed
    print()
    print("=" * 60)
    if failed == 0:
        print(f"All {total} file(s) passed validation.")
    else:
        print(f"Validation complete: {passed} passed, {failed} failed")
    return failed == 0


def _print_failure(result: ValidationResult) -> None:
    print()
    print(f"FAIL: {result.file_path}")
    print("-" * 60)
    if result.errors:
        print("ERRORS:")
        for err in result.errors:
            print(f"  Line {err.line}: {err.message}")
    if result.warnings:
        print("WARNINGS:")
        for warn in result.warnings:
            print(f"  Line {warn.line}: {warn.message}")
    print()
    print(f"Token count: {result.token_count}")
    print(
        f"Result: FAIL ({len(result.errors)} errors, "
        f"{len(result.warnings)} warnings)"
    )
