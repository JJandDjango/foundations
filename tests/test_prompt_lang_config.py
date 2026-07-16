"""Tests for :mod:`prompt_lang.config`.

Covers:

- SPEC §1.3: ``FileRule.allow_reference`` field, defaults False.
- Config passthrough: all FileRule fields survive the YAML roundtrip.
- SPEC §1.2: no ``enforce_tag_order`` / ``tag_order`` fields.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from prompt_lang.config import (
    Config,
    FileRule,
    ValidationConfig,
    load_config,
)


def test_file_rule_has_allow_reference_defaulting_false() -> None:
    """SPEC §1.3 regression."""
    rule = FileRule(pattern="x")
    assert rule.allow_reference is False


def test_file_rule_allow_reference_settable() -> None:
    rule = FileRule(pattern="docs/**/*.md", allow_reference=True)
    assert rule.allow_reference is True


def test_validation_config_has_no_enforce_tag_order() -> None:
    """SPEC §1.2 regression — no tag-order fields."""
    v = ValidationConfig()
    assert not hasattr(v, "enforce_tag_order")
    assert not hasattr(v, "tag_order")


def test_load_config_missing_file_returns_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path / "does-not-exist.yaml")
    assert isinstance(config, Config)
    assert config.file_rules == []
    assert config.validation.required_tags == ["purpose", "instructions"]


def test_load_config_silent_drop_bug_fixed(tmp_path: Path) -> None:
    """Config passthrough: skip_frontmatter / skip_required_tags / allow_reference survive roundtrip."""
    cfg_path = tmp_path / "prompt-lang.config.yaml"
    data = {
        "file_rules": [
            {
                "pattern": "**/README.md",
                "skip_frontmatter": True,
                "skip_required_tags": True,
                "allow_reference": True,
            },
            {
                "pattern": "**/.agentic/agents/*.md",
                "required_tags": ["purpose", "instructions"],
                "forbidden_tags": ["directives"],
            },
        ],
    }
    cfg_path.write_text(yaml.safe_dump(data), encoding="utf-8")

    config = load_config(cfg_path)

    assert len(config.file_rules) == 2
    r1, r2 = config.file_rules
    assert r1.pattern == "**/README.md"
    assert r1.skip_frontmatter is True
    assert r1.skip_required_tags is True
    assert r1.allow_reference is True
    assert r2.pattern == "**/.agentic/agents/*.md"
    assert r2.required_tags == ["purpose", "instructions"]
    assert r2.forbidden_tags == ["directives"]
    assert r2.allow_reference is False


def test_load_config_rejects_non_mapping(tmp_path: Path) -> None:
    cfg_path = tmp_path / "bad.yaml"
    cfg_path.write_text("- a list\n- not a mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="mapping"):
        load_config(cfg_path)


def test_load_config_rejects_non_mapping_file_rule(tmp_path: Path) -> None:
    cfg_path = tmp_path / "bad.yaml"
    cfg_path.write_text(
        yaml.safe_dump({"file_rules": ["not-a-dict"]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="file_rules entry"):
        load_config(cfg_path)


def test_load_config_empty_yaml_returns_defaults(tmp_path: Path) -> None:
    cfg_path = tmp_path / "empty.yaml"
    cfg_path.write_text("", encoding="utf-8")
    config = load_config(cfg_path)
    assert isinstance(config, Config)


def test_default_config_yaml_loads(tmp_path: Path) -> None:
    """The shipped default config (``prompt_lang/prompt-lang.config.yaml``)
    loads cleanly and has the default file rules."""
    config = load_config()
    patterns = {rule.pattern for rule in config.file_rules}
    assert "**/README.md" in patterns
    assert "**/.agentic/agents/*.md" in patterns
    assert "**/.agentic/validators/*.md" in patterns
    assert "**/.agentic/threads/*.md" in patterns

    # README.md is allow-referenced; agent rules are not.
    for rule in config.file_rules:
        if rule.pattern == "**/README.md":
            assert rule.allow_reference is True
        if rule.pattern == "**/.agentic/agents/*.md":
            assert rule.allow_reference is False


def test_default_config_does_not_require_claude_md_directives() -> None:
    """No CLAUDE.md-specific rule in the default config (SPEC §5)."""
    config = load_config()
    for rule in config.file_rules:
        assert "CLAUDE.md" not in rule.pattern, (
            f"CLAUDE.md-specific rule unexpectedly present: {rule!r}"
        )
