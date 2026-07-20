"""Tests for :mod:`theory.config`.

Covers:
- missing file → defaults (AC15)
- empty YAML → defaults
- non-mapping YAML → raises ValueError
- partial keys → dataclass defaults merged
- default config file loads with mode="advisory", min_length=20, "rename" in trivial_classes (AC16)
- custom map_file.path override survives round-trip
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from theory.config import MapConfig, TheoryConfig, load_config


class TestMissingFileReturnsDefaults:
    """missing-file → defaults (AC15)."""

    def test_missing_file_returns_theory_config_instance(self, tmp_path: Path) -> None:
        config = load_config(tmp_path / "does-not-exist.yaml")
        assert isinstance(config, TheoryConfig)

    def test_missing_file_mode_is_advisory(self, tmp_path: Path) -> None:
        config = load_config(tmp_path / "nonexistent.yaml")
        assert config.mode == "advisory"

    def test_missing_file_min_length_is_20(self, tmp_path: Path) -> None:
        config = load_config(tmp_path / "nonexistent.yaml")
        assert config.min_length == 20

    def test_missing_file_no_exception_raised(self, tmp_path: Path) -> None:
        # Must not raise any exception
        config = load_config(tmp_path / "absolutely-not-here.yaml")
        assert config is not None

    def test_missing_file_default_scope_is_everything(self, tmp_path: Path) -> None:
        config = load_config(tmp_path / "nonexistent.yaml")
        assert config.scope == ["**"]

    def test_missing_file_has_rename_in_trivial_classes(self, tmp_path: Path) -> None:
        config = load_config(tmp_path / "nonexistent.yaml")
        assert "rename" in config.trivial_classes


class TestEmptyYamlReturnsDefaults:
    """empty YAML → defaults."""

    def test_empty_file_returns_theory_config(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "empty.yaml"
        cfg_path.write_text("", encoding="utf-8")
        config = load_config(cfg_path)
        assert isinstance(config, TheoryConfig)

    def test_null_yaml_returns_defaults(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "null.yaml"
        cfg_path.write_text("null\n", encoding="utf-8")
        config = load_config(cfg_path)
        assert isinstance(config, TheoryConfig)
        assert config.mode == "advisory"


class TestNonMappingRaisesValueError:
    """non-mapping YAML → raises ValueError with 'mapping' in message."""

    def test_list_yaml_raises_value_error(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "list.yaml"
        cfg_path.write_text("- a\n- b\n", encoding="utf-8")
        with pytest.raises(ValueError, match="mapping"):
            load_config(cfg_path)

    def test_scalar_yaml_raises_value_error(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "scalar.yaml"
        cfg_path.write_text("just a string\n", encoding="utf-8")
        with pytest.raises(ValueError, match="mapping"):
            load_config(cfg_path)


class TestPartialKeysMergeDefaults:
    """partial keys → dataclass defaults merged for missing keys."""

    def test_partial_keys_mode_overridden(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "partial.yaml"
        cfg_path.write_text("mode: gating\n", encoding="utf-8")
        config = load_config(cfg_path)
        assert config.mode == "gating"

    def test_partial_keys_min_length_default_preserved(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "partial.yaml"
        cfg_path.write_text("mode: gating\n", encoding="utf-8")
        config = load_config(cfg_path)
        assert config.min_length == 20

    def test_partial_keys_trivial_classes_default_preserved(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "partial.yaml"
        cfg_path.write_text("mode: gating\n", encoding="utf-8")
        config = load_config(cfg_path)
        assert "rename" in config.trivial_classes


class TestDefaultConfigFileLoads:
    """default config file (no arg) loads with expected values (AC16)."""

    def test_default_mode_is_advisory(self) -> None:
        config = load_config()
        assert config.mode == "advisory"

    def test_default_min_length_is_20(self) -> None:
        config = load_config()
        assert config.min_length == 20

    def test_default_has_rename_in_trivial_classes(self) -> None:
        config = load_config()
        assert "rename" in config.trivial_classes

    def test_default_map_path_is_map_md(self) -> None:
        config = load_config()
        assert config.map.path == "MAP.md"

    def test_default_map_reconcile_is_warn(self) -> None:
        config = load_config()
        assert config.map.reconcile == "warn"


class TestMapOverrideSurvivesRoundTrip:
    """custom map_file.path override survives round-trip."""

    def test_map_path_override(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "custom.yaml"
        cfg_path.write_text(
            "map:\n  path: MY_MAP.md\n  reconcile: warn\n", encoding="utf-8"
        )
        config = load_config(cfg_path)
        assert config.map.path == "MY_MAP.md"

    def test_map_reconcile_override(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "custom.yaml"
        cfg_path.write_text(
            "map:\n  path: CUSTOM.md\n  reconcile: warn\n", encoding="utf-8"
        )
        config = load_config(cfg_path)
        assert config.map.reconcile == "warn"

    def test_map_defaults_when_not_specified(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "no_atlas.yaml"
        cfg_path.write_text("mode: advisory\n", encoding="utf-8")
        config = load_config(cfg_path)
        assert config.map.path == "MAP.md"
        assert config.map.reconcile == "warn"


class TestDefaultScopeIsEverything:
    """Packaged default scope is the generic ["**"] — repos narrow via config."""

    def test_load_config_default_scope(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # chdir keeps any repo-root theory.config.yaml out of cwd discovery.
        monkeypatch.chdir(tmp_path)
        assert load_config().scope == ["**"]

    def test_theory_config_default_scope(self) -> None:
        assert TheoryConfig().scope == ["**"]


# ---------------------------------------------------------------------------
# T1: JudgeConfig dataclass + TheoryConfig new fields (ACs 1, 6, 7)
# ---------------------------------------------------------------------------


class TestJudgeConfigStruct:
    """JudgeConfig dataclass defaults and TheoryConfig new fields (T1 ACs 1, 6, 7)."""

    def test_judge_config_required_fields_construct(self) -> None:
        """AC1: JudgeConfig(model=..., base_url=...) constructs without error."""
        from theory.config import JudgeConfig
        cfg = JudgeConfig(model="gemma", base_url="http://localhost:1234/v1")
        assert cfg.model == "gemma"
        assert cfg.base_url == "http://localhost:1234/v1"

    def test_judge_config_timeout_s_default(self) -> None:
        """AC1: JudgeConfig default timeout_s == 10.0."""
        from theory.config import JudgeConfig
        cfg = JudgeConfig(model="gemma", base_url="http://localhost:1234/v1")
        assert cfg.timeout_s == 10.0

    def test_judge_config_max_diff_chars_default(self) -> None:
        """AC1: JudgeConfig default max_diff_chars == 6000."""
        from theory.config import JudgeConfig
        cfg = JudgeConfig(model="gemma", base_url="http://localhost:1234/v1")
        assert cfg.max_diff_chars == 6000

    def test_judge_config_custom_timeout(self) -> None:
        """JudgeConfig accepts overridden timeout_s."""
        from theory.config import JudgeConfig
        cfg = JudgeConfig(model="m", base_url="http://x", timeout_s=5.0, max_diff_chars=3000)
        assert cfg.timeout_s == 5.0
        assert cfg.max_diff_chars == 3000

    def test_theory_config_trivial_max_lines_default(self) -> None:
        """AC6: TheoryConfig() default trivial_max_lines == 100."""
        assert TheoryConfig().trivial_max_lines == 100

    def test_theory_config_judge_default_is_none(self) -> None:
        """AC7: TheoryConfig() default judge is None."""
        assert TheoryConfig().judge is None

    def test_judge_config_importable_from_config_module(self) -> None:
        """JudgeConfig is importable from theory.config."""
        from theory.config import JudgeConfig  # noqa: F401
        assert True


# ---------------------------------------------------------------------------
# T7: TestJudgeConfig — full YAML block parse (ACs 2–5, 8)
# ---------------------------------------------------------------------------


class TestJudgeConfig:
    """JudgeConfig YAML parsing: full block, missing fields, absent block, trivial_max_lines."""

    def test_ac2_full_judge_block_parsed(self, tmp_path: Path) -> None:
        """AC2: full judge block → all fields correctly populated."""
        from theory.config import JudgeConfig, load_config

        cfg_path = tmp_path / "theory.yaml"
        cfg_path.write_text(
            "judge:\n"
            "  model: \"m\"\n"
            "  base_url: \"http://x\"\n"
            "  timeout_s: 5.0\n"
            "  max_diff_chars: 3000\n",
            encoding="utf-8",
        )
        config = load_config(cfg_path)
        assert isinstance(config.judge, JudgeConfig)
        assert config.judge.model == "m"
        assert config.judge.base_url == "http://x"
        assert config.judge.timeout_s == 5.0
        assert config.judge.max_diff_chars == 3000

    def test_ac3_missing_model_raises_value_error(self, tmp_path: Path) -> None:
        """AC3 (EM-JUDGE-CFG-MISSING-MODEL): missing model → ValueError."""
        cfg_path = tmp_path / "theory.yaml"
        cfg_path.write_text(
            "judge:\n  base_url: \"http://x\"\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="model"):
            load_config(cfg_path)

    def test_ac4_missing_base_url_raises_value_error(self, tmp_path: Path) -> None:
        """AC4 (EM-JUDGE-CFG-MISSING-URL): missing base_url → ValueError."""
        cfg_path = tmp_path / "theory.yaml"
        cfg_path.write_text(
            "judge:\n  model: \"m\"\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="base_url"):
            load_config(cfg_path)

    def test_ac5_no_judge_key_returns_none(self, tmp_path: Path) -> None:
        """AC5: YAML with no 'judge:' key → config.judge is None."""
        cfg_path = tmp_path / "theory.yaml"
        cfg_path.write_text("mode: advisory\n", encoding="utf-8")
        config = load_config(cfg_path)
        assert config.judge is None

    def test_ac8_trivial_max_lines_override(self, tmp_path: Path) -> None:
        """AC8: trivial_max_lines: 0 in YAML → config.trivial_max_lines == 0."""
        cfg_path = tmp_path / "theory.yaml"
        cfg_path.write_text("trivial_max_lines: 0\n", encoding="utf-8")
        config = load_config(cfg_path)
        assert config.trivial_max_lines == 0

    def test_judge_non_mapping_raises_value_error(self, tmp_path: Path) -> None:
        """judge: value must be a mapping, not a scalar."""
        cfg_path = tmp_path / "theory.yaml"
        cfg_path.write_text("judge: not-a-mapping\n", encoding="utf-8")
        with pytest.raises(ValueError, match="mapping"):
            load_config(cfg_path)

    def test_judge_defaults_timeout_and_max_diff_chars(self, tmp_path: Path) -> None:
        """AC2 variant: omitting timeout_s and max_diff_chars uses defaults."""
        from theory.config import JudgeConfig

        cfg_path = tmp_path / "theory.yaml"
        cfg_path.write_text(
            "judge:\n  model: \"m\"\n  base_url: \"http://x\"\n",
            encoding="utf-8",
        )
        config = load_config(cfg_path)
        assert config.judge is not None
        assert config.judge.timeout_s == 10.0
        assert config.judge.max_diff_chars == 6000


# ---------------------------------------------------------------------------
# T7: TestConfigDiscovery — discovery order (ACs 9–11)
# ---------------------------------------------------------------------------


class TestConfigDiscovery:
    """load_config(None) discovery order: explicit > cwd-local > package default."""

    def test_ac9_explicit_path_wins(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC9: explicit path wins even when cwd has a theory.config.yaml."""
        # Create an explicit config with gating
        explicit = tmp_path / "explicit.yaml"
        explicit.write_text("mode: gating\n", encoding="utf-8")

        # Create cwd-local config with different content
        cwd_dir = tmp_path / "cwd"
        cwd_dir.mkdir()
        (cwd_dir / "theory.config.yaml").write_text("mode: advisory\n", encoding="utf-8")

        monkeypatch.chdir(cwd_dir)
        config = load_config(explicit)
        assert config.mode == "gating"

    def test_ac10_cwd_file_used_when_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC10: load_config(None) from dir with theory.config.yaml uses it."""
        cwd_dir = tmp_path / "cwd"
        cwd_dir.mkdir()
        (cwd_dir / "theory.config.yaml").write_text("mode: gating\n", encoding="utf-8")

        monkeypatch.chdir(cwd_dir)
        config = load_config(None)
        assert config.mode == "gating"

    def test_ac11_em_discovery_cwd_missing_falls_to_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC11 (EM-DISCOVERY-CWD-MISSING): no cwd config → package default → advisory."""
        # Use a directory with no theory.config.yaml
        cwd_dir = tmp_path / "empty_cwd"
        cwd_dir.mkdir()

        monkeypatch.chdir(cwd_dir)
        config = load_config(None)
        # Package default is advisory
        assert config.mode == "advisory"
