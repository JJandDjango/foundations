"""Tests for the house-standard loader (codestandard.standard)."""

from __future__ import annotations

from pathlib import Path

import pytest

from codestandard.standard import _default_standard_path, load_standard


_VALID = "version: 0.0.1\nrules:\n  cognitive_complexity:\n    tier: 1\n    max: 15\n"


class TestLoadStandard:
    def test_valid_fixture_returns_version_and_rules(self, tmp_path: Path):
        path = tmp_path / "code_standard.yaml"
        path.write_text(_VALID, encoding="utf-8")
        data = load_standard(path)
        assert "version" in data
        assert isinstance(data["rules"], dict)
        assert "cognitive_complexity" in data["rules"]

    def test_missing_file_raises_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_standard(tmp_path / "does_not_exist.yaml")

    def test_missing_rules_key_raises_value_error(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text("version: 0.0.1\n", encoding="utf-8")
        with pytest.raises(ValueError):
            load_standard(path)

    def test_default_path_last_two_components(self):
        assert _default_standard_path().parts[-2:] == ("codestandard", "code_standard.yaml")

    def test_default_path_loads_real_standard(self):
        """No-arg load resolves and reads the committed repo standard."""
        data = load_standard()
        assert isinstance(data["rules"], dict) and data["rules"]
