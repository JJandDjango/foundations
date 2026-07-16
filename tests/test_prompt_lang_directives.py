"""Tests for :mod:`prompt_lang.directives`.

Covers the directive grammar (SPEC §4):

- CHAIN accepts ASCII ``->`` in addition to ``→``.
- REQUIRE permits quoted paths with spaces.
"""

from __future__ import annotations

from prompt_lang.config import DirectiveConfig, InstructionConfig
from prompt_lang.directives import (
    Directive,
    extract_instruction_steps,
    parse_directives,
    validate_directive,
    validate_instruction_step,
)


# ---------------------------------------------------------------------------
# parse_directives.
# ---------------------------------------------------------------------------


def test_parse_directives_recognizes_all_four_keywords() -> None:
    content = "\n".join(
        [
            "DELEGATE @dev WHEN fix, code",
            "DEFAULT @orchestrator",
            "CHAIN impl: @dev -> @qa",
            "REQUIRE agents/orchestrator.md ON session_start",
        ]
    )
    directives = parse_directives(content)
    assert {d.type for d in directives} == {"DELEGATE", "DEFAULT", "CHAIN", "REQUIRE"}


def test_parse_directives_skips_blanks_and_comments() -> None:
    content = "\n".join(
        [
            "# a comment",
            "",
            "DELEGATE @dev WHEN fix",
            "# another comment",
        ]
    )
    directives = parse_directives(content)
    assert len(directives) == 1
    assert directives[0].type == "DELEGATE"


# ---------------------------------------------------------------------------
# validate_directive — default patterns from DirectiveConfig.
# ---------------------------------------------------------------------------


class TestDefaultPatterns:
    def test_valid_delegate(self) -> None:
        ok, _ = validate_directive(
            "DELEGATE @developer WHEN fix, code, refactor",
            DirectiveConfig(),
        )
        assert ok

    def test_invalid_delegate_missing_when(self) -> None:
        ok, reason = validate_directive(
            "DELEGATE @developer", DirectiveConfig(),
        )
        assert not ok
        assert "DELEGATE" in reason

    def test_valid_default(self) -> None:
        ok, _ = validate_directive("DEFAULT @orchestrator", DirectiveConfig())
        assert ok


# ---------------------------------------------------------------------------
# SPEC §4: CHAIN accepts ASCII "->" in addition to "→".
# ---------------------------------------------------------------------------


class TestChainArrowFix:
    def test_unicode_arrow_still_accepted(self) -> None:
        ok, _ = validate_directive(
            "CHAIN impl: @a → @b → @c", DirectiveConfig(),
        )
        assert ok

    def test_ascii_arrow_accepted(self) -> None:
        """SPEC §4 regression."""
        ok, reason = validate_directive(
            "CHAIN impl: @a -> @b -> @c", DirectiveConfig(),
        )
        assert ok, reason

    def test_mixed_arrows_accepted(self) -> None:
        ok, _ = validate_directive(
            "CHAIN impl: @a -> @b → @c", DirectiveConfig(),
        )
        assert ok

    def test_chain_without_any_arrow_rejected(self) -> None:
        ok, _ = validate_directive(
            "CHAIN impl: @a @b", DirectiveConfig(),
        )
        assert not ok


# ---------------------------------------------------------------------------
# SPEC §4: REQUIRE permits quoted paths with spaces.
# ---------------------------------------------------------------------------


class TestRequireQuotedPaths:
    def test_require_unquoted_no_spaces_still_works(self) -> None:
        ok, _ = validate_directive(
            "REQUIRE agents/orchestrator.md ON session_start",
            DirectiveConfig(),
        )
        assert ok

    def test_require_quoted_path_with_spaces(self) -> None:
        """SPEC §4 regression."""
        ok, reason = validate_directive(
            'REQUIRE "my docs/orchestrator.md" ON session_start',
            DirectiveConfig(),
        )
        assert ok, reason

    def test_require_quoted_path_no_spaces(self) -> None:
        """Quoting should also work even without spaces."""
        ok, _ = validate_directive(
            'REQUIRE "plain.md" ON session_start',
            DirectiveConfig(),
        )
        assert ok

    def test_require_unquoted_with_space_still_rejected(self) -> None:
        """Spaces must be quoted; bare spaces are ambiguous syntax."""
        ok, _ = validate_directive(
            "REQUIRE my docs/file.md ON session_start",
            DirectiveConfig(),
        )
        assert not ok


# ---------------------------------------------------------------------------
# Instruction-step action keywords.
# ---------------------------------------------------------------------------


class TestInstructionSteps:
    def test_step_with_action_keyword_ok(self) -> None:
        """With enforcement on, an action-keyword step passes."""
        ok, _ = validate_instruction_step(
            "1. ROUTE to @developer", InstructionConfig(enforce_actions=True),
        )
        assert ok

    def test_step_without_action_keyword_rejected(self) -> None:
        """With enforcement on, a bare numbered step fails."""
        ok, reason = validate_instruction_step(
            "1. just do the thing", InstructionConfig(enforce_actions=True),
        )
        assert not ok
        assert "action keyword" in reason

    def test_non_numbered_lines_are_skipped(self) -> None:
        ok, _ = validate_instruction_step(
            "This is prose, not a numbered step.",
            InstructionConfig(enforce_actions=True),
        )
        assert ok

    def test_enforcement_default_is_off(self) -> None:
        """Default InstructionConfig has enforce_actions=False; any step passes."""
        ok, _ = validate_instruction_step("1. anything goes", InstructionConfig())
        assert ok


def test_extract_instruction_steps() -> None:
    content = "1. first\n2. second\nprose line\n3. third\n"
    steps = extract_instruction_steps(content)
    assert len(steps) == 3
    assert steps[0][0] == "1. first"
    assert steps[2][1] == 4  # line number


def test_directive_dataclass() -> None:
    d = Directive(type="DELEGATE", content="DELEGATE @x WHEN y", line_number=5)
    assert d.type == "DELEGATE"
    assert d.line_number == 5
