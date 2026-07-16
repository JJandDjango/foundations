"""Tests for :mod:`prompt_lang.validator` — end-to-end + CLI."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from prompt_lang.config import Config, FileRule
from prompt_lang.validator import (
    EXIT_CONFIG_ERROR,
    EXIT_FILE_NOT_FOUND,
    EXIT_SUCCESS,
    EXIT_VALIDATION_ERROR,
    main,
    match_file_rule,
    validate_file,
)


# ---------------------------------------------------------------------------
# File-rule matching (SPEC §5 Windows path handling).
# ---------------------------------------------------------------------------


class TestMatchFileRule:
    def test_fnmatch_against_posix_path(self) -> None:
        """Backslashes are normalized to forward slashes before matching."""
        config = Config(
            file_rules=[FileRule(pattern="**/.agentic/agents/*.md")],
        )
        rule = match_file_rule(
            Path(r".agentic\agents\dev.md"), config,
        )
        assert rule is not None
        assert rule.pattern == "**/.agentic/agents/*.md"

    def test_no_match_returns_none(self) -> None:
        config = Config(file_rules=[FileRule(pattern="x/*.md")])
        assert match_file_rule(Path("y/a.md"), config) is None

    def test_first_match_wins(self) -> None:
        config = Config(
            file_rules=[
                FileRule(pattern="**/*.md", allow_reference=True),
                FileRule(pattern="**/README.md", required_tags=["purpose"]),
            ],
        )
        rule = match_file_rule(Path("README.md"), config)
        # First rule wins — the broader ``**/*.md``.
        assert rule is not None
        assert rule.allow_reference is True

    def test_absolute_posix_path_matches_globstar_prefix(self) -> None:
        """Leading ``/`` on absolute POSIX paths must not block a ``**/`` rule.

        ``**/`` compiles to ``(?:[^/]+/)*`` which cannot consume a leading
        separator, so ``match_file_rule`` strips the leading ``/`` before
        matching. Without this, every absolute path on Linux would silently
        miss every ``**/``-prefixed rule.
        """
        config = Config(
            file_rules=[FileRule(pattern="**/.agentic/agents/*.md")],
        )
        rule = match_file_rule(
            Path("/tmp/proj/.agentic/agents/dev.md"), config,
        )
        assert rule is not None
        assert rule.pattern == "**/.agentic/agents/*.md"


# ---------------------------------------------------------------------------
# validate_file — end-to-end.
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


class TestValidateFile:
    def test_minimal_valid_prompt_passes(self, tmp_path: Path) -> None:
        content = textwrap.dedent(
            """\
            ---
            name: dev
            description: Developer agent
            ---

            <purpose>Implement features.</purpose>
            <instructions>
            1. Read the spec.
            2. Write the code.
            </instructions>
            """
        )
        path = _write(tmp_path, "dev.md", content)
        result = validate_file(path, Config())
        assert result.passed, result.errors

    def test_ambiguous_language_in_instructions_fails(self, tmp_path: Path) -> None:
        content = textwrap.dedent(
            """\
            ---
            name: dev
            description: Developer
            ---

            <purpose>x</purpose>
            <instructions>
            1. Maybe do this
            2. You could consider that
            </instructions>
            """
        )
        path = _write(tmp_path, "dev.md", content)
        result = validate_file(path, Config())
        assert not result.passed
        msgs = " ".join(e.message for e in result.errors)
        assert "maybe" in msgs.lower() or "Maybe" in msgs

    def test_ambiguous_language_skipped_when_semantic_check_off(
        self, tmp_path: Path,
    ) -> None:
        content = textwrap.dedent(
            """\
            ---
            name: dev
            description: Developer
            ---

            <purpose>x</purpose>
            <instructions>
            1. Maybe do this
            </instructions>
            """
        )
        path = _write(tmp_path, "dev.md", content)
        config = Config()
        config.validation.semantic_check = False
        result = validate_file(path, config)
        assert result.passed, result.errors

    def test_file_rule_required_tag_enforced(self, tmp_path: Path) -> None:
        """A rule requiring <output> tags a file missing one."""
        content = textwrap.dedent(
            """\
            ---
            name: dev
            description: Developer
            ---

            <purpose>x</purpose>
            <instructions>1.</instructions>
            """
        )
        # Nest under an .agentic/agents/ path so the default file_rule matches
        # and contributes its required_tags.
        subdir = tmp_path / ".agentic" / "agents"
        subdir.mkdir(parents=True)
        path = subdir / "dev.md"
        path.write_text(content, encoding="utf-8")

        config = Config(
            file_rules=[
                FileRule(
                    pattern="**/.agentic/agents/*.md",
                    required_tags=["output"],
                ),
            ],
        )
        result = validate_file(path, config)
        assert not result.passed
        assert any("<output>" in e.message for e in result.errors)

    def test_file_rule_forbidden_tag_enforced(self, tmp_path: Path) -> None:
        content = textwrap.dedent(
            """\
            ---
            name: dev
            description: Developer
            ---

            <purpose>x</purpose>
            <instructions>1.</instructions>
            <directives>
            DELEGATE @dev WHEN fix
            </directives>
            """
        )
        path = _write(tmp_path, "dev.md", content)
        config = Config(
            file_rules=[
                FileRule(pattern="**/*.md", forbidden_tags=["directives"]),
            ],
        )
        result = validate_file(path, config)
        assert not result.passed
        assert any("forbids" in e.message for e in result.errors)

    def test_reference_true_authorized(self, tmp_path: Path) -> None:
        content = textwrap.dedent(
            """\
            ---
            name: readme
            description: Docs
            reference: true
            ---

            # Just some docs
            No tags needed.
            """
        )
        path = _write(tmp_path, "README.md", content)
        config = Config(
            file_rules=[
                FileRule(pattern="**/README.md", allow_reference=True),
            ],
        )
        result = validate_file(path, config)
        assert result.passed, result.errors

    def test_reference_true_unauthorized(self, tmp_path: Path) -> None:
        content = textwrap.dedent(
            """\
            ---
            name: cheat
            description: trying to skip validation
            reference: true
            ---

            no tags
            """
        )
        path = _write(tmp_path, "cheat.md", content)
        result = validate_file(path, Config())  # no file_rules
        assert not result.passed
        assert any("not authorized" in e.message for e in result.errors)

    def test_invalid_directive_in_directives_block_flagged(self, tmp_path: Path) -> None:
        content = textwrap.dedent(
            """\
            ---
            name: orch
            description: orch
            ---

            <purpose>x</purpose>
            <instructions>1.</instructions>
            <directives>
            DELEGATE bogus format
            </directives>
            """
        )
        config = Config()
        config.validation.optional_tags.append("directives")  # already there; keep explicit
        path = _write(tmp_path, "orch.md", content)
        result = validate_file(path, config)
        assert not result.passed
        assert any("Invalid directive" in e.message for e in result.errors)


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


class TestCli:
    def test_main_path_not_found(self, tmp_path: Path) -> None:
        rc = main([str(tmp_path / "missing.md")])
        assert rc == EXIT_FILE_NOT_FOUND

    def test_main_single_file_pass(self, tmp_path: Path) -> None:
        content = textwrap.dedent(
            """\
            ---
            name: dev
            description: Developer
            ---

            <purpose>x</purpose>
            <instructions>1. Read the spec.</instructions>
            """
        )
        path = _write(tmp_path, "dev.md", content)
        rc = main([str(path)])
        assert rc == EXIT_SUCCESS

    def test_main_single_file_fail(self, tmp_path: Path) -> None:
        path = _write(tmp_path, "bad.md", "no frontmatter\n")
        rc = main([str(path)])
        assert rc == EXIT_VALIDATION_ERROR

    def test_main_directory_mode(self, tmp_path: Path) -> None:
        good = textwrap.dedent(
            """\
            ---
            name: dev
            description: Developer
            ---

            <purpose>x</purpose>
            <instructions>1.</instructions>
            """
        )
        _write(tmp_path, "a.md", good)
        _write(tmp_path, "b.md", good)
        rc = main([str(tmp_path)])
        assert rc == EXIT_SUCCESS

    def test_main_no_semantic_flag_allows_maybe(self, tmp_path: Path) -> None:
        content = textwrap.dedent(
            """\
            ---
            name: dev
            description: Developer
            ---

            <purpose>x</purpose>
            <instructions>
            1. Maybe do this
            </instructions>
            """
        )
        path = _write(tmp_path, "dev.md", content)
        rc = main([str(path), "--no-semantic"])
        assert rc == EXIT_SUCCESS

    def test_main_config_error_exit_code(self, tmp_path: Path) -> None:
        bad_config = tmp_path / "bad.yaml"
        bad_config.write_text("- a list\n", encoding="utf-8")
        target = _write(tmp_path, "dev.md", "---\nname: x\ndescription: y\n---\n<purpose>x</purpose>\n<instructions>1.</instructions>\n")
        rc = main([str(target), "--config", str(bad_config)])
        assert rc == EXIT_CONFIG_ERROR
