"""Tests for the codestandard CLI (codestandard.cli.main)."""

from __future__ import annotations

from pathlib import Path

from codestandard import cli
from codestandard.core import CodeFinding


class _FakeChecker:
    def __init__(self, findings):
        self._findings = findings

    def run(self, project_root, standard):
        return list(self._findings)


def _ok_standard(monkeypatch):
    monkeypatch.setattr(cli, "load_standard", lambda path=None: {"version": "0.0.1", "rules": {}})


class TestCli:
    def test_exit_zero_when_no_findings(self, monkeypatch, tmp_path):
        _ok_standard(monkeypatch)
        monkeypatch.setattr(cli, "_build_checker", lambda: _FakeChecker([]))
        assert cli.main([str(tmp_path)]) == 0

    def test_exit_one_and_stdout_when_findings(self, monkeypatch, tmp_path, capsys):
        _ok_standard(monkeypatch)
        finding = CodeFinding(
            rule="params", file=Path("a.py"), line=1, measured=6, limit=5,
            message="Too many arguments (6 > 5)",
        )
        monkeypatch.setattr(cli, "_build_checker", lambda: _FakeChecker([finding]))
        assert cli.main([str(tmp_path)]) == 1
        assert "params  a.py:1  6/5  Too many arguments (6 > 5)" in capsys.readouterr().out

    def test_exit_one_and_stderr_on_missing_standard(self, monkeypatch, tmp_path, capsys):
        def _raise(path=None):
            raise FileNotFoundError("nope")

        monkeypatch.setattr(cli, "load_standard", _raise)
        assert cli.main([str(tmp_path)]) == 1
        assert "standard not found" in capsys.readouterr().err

    def test_standard_flag_forwarded(self, monkeypatch, tmp_path):
        seen = {}

        def _load(path=None):
            seen["path"] = path
            return {"version": "0.0.1", "rules": {}}

        monkeypatch.setattr(cli, "load_standard", _load)
        monkeypatch.setattr(cli, "_build_checker", lambda: _FakeChecker([]))
        cli.main([str(tmp_path), "--standard", "/custom/std.yaml"])
        assert seen["path"] == Path("/custom/std.yaml")
