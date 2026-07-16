"""Directive parsing / validation for routing rules (SPEC §4).

Parses DELEGATE / DEFAULT / CHAIN / REQUIRE directive lines. Grammar
notes baked into the regexes (via ``DirectiveConfig``):

- CHAIN accepts ASCII ``->`` in addition to the Unicode arrow ``→``.
- REQUIRE permits quoted paths that contain spaces.

Not every consumer routes via directives; wherever a ``<directives>``
block appears, the syntax is validated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from prompt_lang.config import DirectiveConfig, InstructionConfig


_STEP_NUMBER_PATTERN = re.compile(r"^\s*(\d+)\.\s+(.+)$")


@dataclass
class Directive:
    """A single directive line extracted from a ``<directives>`` block."""

    type: str
    content: str
    line_number: int


def parse_directives(content: str) -> list[Directive]:
    """Extract directive lines from a ``<directives>`` block.

    Skips blank lines and ``#`` comments. ``line_number`` is 1-indexed
    within the block content (not the full file).
    """
    out: list[Directive] = []
    for i, raw in enumerate(content.strip().split("\n"), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        for keyword in ("DELEGATE", "DEFAULT", "CHAIN", "REQUIRE"):
            if line.startswith(keyword):
                out.append(Directive(type=keyword, content=line, line_number=i))
                break
    return out


def validate_directive(line: str, config: DirectiveConfig) -> tuple[bool, str]:
    """Validate a single directive line against its regex pattern.

    Returns ``(True, "")`` on pass, ``(False, reason)`` on fail.
    """
    line = line.strip()
    directive_type: str | None = None
    for keyword in config.keywords:
        if line.startswith(keyword):
            directive_type = keyword
            break
    if directive_type is None:
        return (
            False,
            f"Unknown directive keyword. Expected one of: {', '.join(config.keywords)}",
        )
    pattern = config.patterns.get(directive_type)
    if not pattern:
        return (
            False,
            f"No validation pattern found for directive type: {directive_type}",
        )
    if not re.match(pattern, line):
        return (
            False,
            f"Invalid {directive_type} syntax. Expected pattern: {pattern}",
        )
    return True, ""


def validate_instruction_step(line: str, config: InstructionConfig) -> tuple[bool, str]:
    """Check that a numbered instruction step begins with an allowed action.

    Non-numbered lines are skipped (return True). Disabled when
    ``config.enforce_actions`` is False.
    """
    if not config.enforce_actions:
        return True, ""

    match = _STEP_NUMBER_PATTERN.match(line.strip())
    if not match:
        return True, ""

    content = match.group(2).strip()
    first_word = content.split()[0] if content.split() else ""
    if first_word not in config.action_keywords:
        return (
            False,
            f"Instruction step must start with an action keyword. "
            f"Found: '{first_word}', expected one of: "
            f"{', '.join(config.action_keywords)}",
        )
    return True, ""


def extract_instruction_steps(content: str) -> list[tuple[str, int]]:
    """Extract numbered steps (``^\\d+\\.`` lines) from an ``<instructions>``
    block. 1-indexed line numbers within the block."""
    out: list[tuple[str, int]] = []
    for i, raw in enumerate(content.strip().split("\n"), start=1):
        if _STEP_NUMBER_PATTERN.match(raw):
            out.append((raw.strip(), i))
    return out
