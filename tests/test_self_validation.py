"""The standard applies to itself: this repo's own artifacts conform.

Self-application is a THEORY success criterion — the repo that ships the
validator must pass it.
"""
from __future__ import annotations

from pathlib import Path

from prompt_lang.config import load_config
from prompt_lang.validator import match_file_rule, validate_file

REPO = Path(__file__).resolve().parent.parent


def test_skills_rule_claims_skill_md_paths() -> None:
    """The SKILL.md artifact class (SPEC §5) matches both layouts."""
    config = load_config()
    for candidate in ("skills/refactor/SKILL.md", ".claude/skills/x/SKILL.md"):
        rule = match_file_rule(Path(candidate), config)
        assert rule is not None, candidate
        assert "purpose" in rule.required_tags, candidate
        assert "instructions" in rule.required_tags, candidate


def test_refactor_skill_passes_default_config() -> None:
    result = validate_file(REPO / "skills" / "refactor" / "SKILL.md", load_config())
    assert result.passed, [e.message for e in result.errors]
