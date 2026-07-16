"""Tests for :mod:`prompt_lang.parser`.

Covers:

- SPEC §3: tiktoken required (no fallback). Parser imports at module level.
- SPEC §1.3: ``reference: true`` rule-gated via ``FileRule.allow_reference``.
- SPEC §1.2: tag order deliberately not validated.
"""

from __future__ import annotations

import textwrap

from prompt_lang.config import Config, FileRule, ValidationConfig
from prompt_lang.errors import ValidationResult
from prompt_lang.parser import parse_content


def _parse(content: str, file_rule: FileRule | None = None, config: Config | None = None):
    result = ValidationResult(file_path="<test>.md")
    if config is None:
        config = Config()
    return parse_content(content, result, config, file_rule)


# ---------------------------------------------------------------------------
# Happy paths.
# ---------------------------------------------------------------------------


def test_minimal_valid_prompt() -> None:
    content = textwrap.dedent(
        """\
        ---
        name: x
        description: y
        ---

        <purpose>do the thing</purpose>
        <instructions>
        1. do it
        </instructions>
        """
    )
    _, result = _parse(content)
    assert result.passed, result.errors


def test_token_count_populated() -> None:
    """SPEC §3 tiktoken-required regression: count is non-zero and deterministic."""
    _, result = _parse("---\nname: x\ndescription: y\n---\n\n<purpose>p</purpose>\n<instructions>1.</instructions>\n")
    assert result.token_count > 0


# ---------------------------------------------------------------------------
# Frontmatter.
# ---------------------------------------------------------------------------


def test_missing_frontmatter_delimiter() -> None:
    _, result = _parse("no frontmatter at all\n<purpose>x</purpose>")
    assert not result.passed
    assert any("Missing YAML frontmatter" in e.message for e in result.errors)


def test_malformed_frontmatter_missing_closing_delimiter() -> None:
    _, result = _parse("---\nname: x\ndescription: y\n(no closing)\n<purpose>x</purpose>")
    assert not result.passed
    assert any("closing" in e.message.lower() for e in result.errors)


def test_missing_required_frontmatter_field() -> None:
    _, result = _parse("---\nname: x\n---\n\n<purpose>x</purpose>\n<instructions>1.</instructions>")
    assert any("description" in e.message for e in result.errors)


# ---------------------------------------------------------------------------
# Tags.
# ---------------------------------------------------------------------------


def test_missing_required_tag_purpose() -> None:
    _, result = _parse("---\nname: x\ndescription: y\n---\n\n<instructions>1.</instructions>")
    assert any("purpose" in e.message for e in result.errors)


def test_unrecognized_tag_is_error() -> None:
    content = textwrap.dedent(
        """\
        ---
        name: x
        description: y
        ---

        <purpose>p</purpose>
        <instructions>1.</instructions>
        <bogus>huh</bogus>
        """
    )
    _, result = _parse(content)
    assert any("Unrecognized tag" in e.message and "bogus" in e.message for e in result.errors)


def test_unclosed_tag_detected() -> None:
    content = textwrap.dedent(
        """\
        ---
        name: x
        description: y
        ---

        <purpose>p</purpose>
        <instructions>
        forgot to close
        """
    )
    _, result = _parse(content)
    assert any("Unclosed tag" in e.message for e in result.errors)


def test_nested_tag_detected() -> None:
    content = textwrap.dedent(
        """\
        ---
        name: x
        description: y
        ---

        <purpose>p</purpose>
        <instructions>
        1. step
        <context>nested</context>
        </instructions>
        """
    )
    _, result = _parse(content)
    assert any("Nested tag" in e.message for e in result.errors)


# ---------------------------------------------------------------------------
# SPEC §1.3 — reference: true rule-gating.
# ---------------------------------------------------------------------------


class TestReferenceGating:
    def _ref_content(self) -> str:
        return textwrap.dedent(
            """\
            ---
            name: x
            description: y
            reference: true
            ---

            Random markdown; no tags required because reference: true.
            """
        )

    def test_reference_without_allow_reference_rejected(self) -> None:
        """No matching file_rule → unauthorized."""
        _, result = _parse(self._ref_content(), file_rule=None)
        assert not result.passed
        assert any("not authorized" in e.message for e in result.errors)

    def test_reference_with_rule_but_no_allow_rejected(self) -> None:
        """Rule matches but allow_reference is False."""
        rule = FileRule(pattern="**/*.md", allow_reference=False)
        _, result = _parse(self._ref_content(), file_rule=rule)
        assert not result.passed
        assert any(
            "not authorized" in e.message and "**/*.md" in e.message
            for e in result.errors
        )

    def test_reference_with_allow_succeeds(self) -> None:
        rule = FileRule(pattern="**/README.md", allow_reference=True)
        _, result = _parse(self._ref_content(), file_rule=rule)
        assert result.passed, result.errors

    def test_reference_error_message_lists_allowed_patterns(self) -> None:
        """Error message must point the author at the authorized patterns."""
        config = Config(
            file_rules=[
                FileRule(pattern="**/README.md", allow_reference=True),
                FileRule(pattern="docs/**/*.md", allow_reference=True),
                FileRule(pattern="**/.agentic/agents/*.md"),  # not authorized
            ],
        )
        # Provide no matching rule so the error fires, but we still expect
        # the listed authorized patterns to come from the config's
        # allow_reference-enabled rules.
        _, result = _parse(self._ref_content(), file_rule=None, config=config)
        assert not result.passed
        msg = result.errors[0].message
        assert "**/README.md" in msg
        assert "docs/**/*.md" in msg
        # Non-authorized pattern must NOT be listed as allowed.
        assert ".agentic/agents" not in msg


# ---------------------------------------------------------------------------
# SPEC §1.2 — tag order not validated.
# ---------------------------------------------------------------------------


def test_out_of_order_tags_no_longer_flagged() -> None:
    """Tag order is editorial (SPEC §1.2); out-of-order tags pass."""
    content = textwrap.dedent(
        """\
        ---
        name: x
        description: y
        ---

        <instructions>
        1. do it
        </instructions>

        <purpose>p</purpose>
        """
    )
    _, result = _parse(content)
    assert result.passed, result.errors


# ---------------------------------------------------------------------------
# skip_frontmatter / skip_required_tags passthrough (config regression).
# ---------------------------------------------------------------------------


def test_skip_frontmatter_rule_honored() -> None:
    rule = FileRule(pattern="**/CLAUDE.md", skip_frontmatter=True)
    # No frontmatter at all — normally an error, but skip_frontmatter suppresses it.
    _, result = _parse(
        "Just prose.\n<purpose>p</purpose>\n<instructions>1.</instructions>",
        file_rule=rule,
    )
    # There should be no "Missing YAML frontmatter" error.
    assert not any(
        "Missing YAML frontmatter" in e.message for e in result.errors
    )


def test_skip_required_tags_rule_honored() -> None:
    rule = FileRule(pattern="**/primitives/*.md", skip_required_tags=True)
    content = textwrap.dedent(
        """\
        ---
        name: x
        description: y
        ---

        Just prose, no required tags.
        """
    )
    _, result = _parse(content, file_rule=rule)
    assert not any("Missing required tag" in e.message for e in result.errors)
