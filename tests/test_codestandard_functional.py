"""Functional acceptance tests for codestandard_engine_v0 — all 10 ACs. QA-owned.

AC-1..AC-9 are asserted here directly. AC-10 ("full suite -m 'not live' exits 0 at
>= 3468") is a meta-criterion verified by running the suite itself, not by an
in-test assertion (that would recurse).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from codestandard import cli
from codestandard.checks import python_checker
from codestandard.checks.python_checker import PythonChecker
from codestandard.core import CodeChecker, CodeFinding
from codestandard.standard import _default_standard_path, load_standard


_STANDARD = {
    "version": "0.0.1",
    "rules": {
        "cognitive_complexity": {"max": 15},
        "cyclomatic_complexity": {"max": 10},
        "params": {"max": 5},
        "returns": {"max": 6},
        "function_length": {"max": 50},
    },
}

_CLEAN_SOURCE = "def ok(value):\n    return value + 1\n"
_COMPLEX_SOURCE = (
    "def tangled(a, b, c, d, e, f):\n"
    "    total = 0\n"
    "    for x in range(a):\n"
    "        if x % 2 == 0:\n"
    "            total += 1\n"
    "        elif x % 3 == 0:\n"
    "            total += 2\n"
    "        elif x % 5 == 0:\n"
    "            total += 3\n"
    "        else:\n"
    "            total -= 1\n"
    "        if b and c:\n"
    "            total += x\n"
    "        if d or e:\n"
    "            total -= x\n"
    "        while total > 100:\n"
    "            total -= 10\n"
    "            if total % 7 == 0:\n"
    "                break\n"
    "    if f:\n"
    "        return total\n"
    "    return -total\n"
)


class _FakeProc:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


def test_ac2_default_path_and_real_standard_loads():
    assert _default_standard_path().parts[-2:] == ("codestandard", "code_standard.yaml")
    assert isinstance(load_standard()["rules"], dict)


def test_ac3_load_standard_error_modes(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_standard(tmp_path / "missing.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: 0.0.1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_standard(bad)


def test_ac4_5_6_tool_invocation_and_decode(monkeypatch, tmp_path):
    capture = []

    def fake_run(cmd, **kwargs):
        capture.append((cmd, kwargs))
        return _FakeProc(stdout="[]" if cmd[0] == "ruff" else "", returncode=0)

    monkeypatch.setattr(python_checker.subprocess, "run", fake_run)
    list(PythonChecker().run(tmp_path, _STANDARD))
    ruff = next(cmd for cmd, _ in capture if cmd[0] == "ruff")
    select = ruff[ruff.index("--select") + 1]
    assert all(c in select for c in ("C901", "PLR0911", "PLR0913", "PLR0915"))  # AC-4
    assert "PLR0912" not in select  # AC-4
    assert any("--select=CCR001" in cmd for cmd, _ in capture)  # AC-5
    for _, kwargs in capture:  # AC-6
        assert kwargs.get("encoding") == "utf-8" and kwargs.get("errors") == "replace"


def test_ac7_8_finding_fields_and_sort_order():
    f_b = CodeFinding(rule="returns", file=Path("b.py"), line=3, measured=7, limit=6, message="Too many return statements (7 > 6)")
    f_a = CodeFinding(rule="params", file=Path("a.py"), line=8, measured=6, limit=5, message="Too many arguments (6 > 5)")

    class _Stub:
        rule = "stub"

        def run(self, project_root, standard):
            return [f_b, f_a]

    out = CodeChecker([_Stub()]).run(Path("."), _STANDARD)
    assert out == [f_a, f_b]  # AC-8: a.py sorts before b.py
    for finding in out:  # AC-7: every field present + typed
        assert isinstance(finding.rule, str) and finding.rule
        assert isinstance(finding.file, Path)
        assert isinstance(finding.line, int) and finding.line >= 1
        assert isinstance(finding.measured, int) and isinstance(finding.limit, int)
        assert isinstance(finding.message, str) and finding.message


def test_ac9_stdout_line_format():
    finding = CodeFinding(
        rule="params", file=Path("src/x.py"), line=12, measured=6, limit=5,
        message="Too many arguments (6 > 5)",
    )
    assert str(finding) == "params  src/x.py:12  6/5  Too many arguments (6 > 5)"


@pytest.mark.slow
def test_ac1_cli_exit_codes_end_to_end(tmp_path):
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "ok.py").write_text(_CLEAN_SOURCE, encoding="utf-8")
    assert cli.main([str(clean)]) == 0  # AC-1: no findings -> exit 0

    dirty = tmp_path / "dirty"
    dirty.mkdir()
    (dirty / "bad.py").write_text(_COMPLEX_SOURCE, encoding="utf-8")
    assert cli.main([str(dirty)]) == 1  # AC-1: findings -> exit 1
