"""PythonChecker: mocked-subprocess unit tests + one @slow real-tool test."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codestandard.checks import python_checker
from codestandard.checks.python_checker import PythonChecker


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
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _patch(monkeypatch, *, ruff_stdout="[]", flake8_stdout="", capture=None):
    def fake_run(cmd, **kwargs):
        if capture is not None:
            capture.append((cmd, kwargs))
        if cmd[0] == "ruff":
            rc = 1 if ruff_stdout.strip() not in ("", "[]") else 0
            return _FakeProc(stdout=ruff_stdout, returncode=rc)
        return _FakeProc(stdout=flake8_stdout, returncode=1 if flake8_stdout.strip() else 0)

    monkeypatch.setattr(python_checker.subprocess, "run", fake_run)


class TestInvocation:
    def test_ruff_select_has_codes_not_plr0912(self, monkeypatch, tmp_path):
        capture = []
        _patch(monkeypatch, capture=capture)
        list(PythonChecker().run(tmp_path, _STANDARD))
        ruff = next(cmd for cmd, _ in capture if cmd[0] == "ruff")
        select = ruff[ruff.index("--select") + 1]
        assert all(c in select for c in ("C901", "PLR0911", "PLR0913", "PLR0915"))
        assert "PLR0912" not in select

    def test_flake8_selects_ccr001(self, monkeypatch, tmp_path):
        capture = []
        _patch(monkeypatch, capture=capture)
        list(PythonChecker().run(tmp_path, _STANDARD))
        assert any("--select=CCR001" in cmd for cmd, _ in capture)

    def test_decode_utf8_replace(self, monkeypatch, tmp_path):
        capture = []
        _patch(monkeypatch, capture=capture)
        list(PythonChecker().run(tmp_path, _STANDARD))
        assert capture
        for _, kwargs in capture:
            assert kwargs.get("encoding") == "utf-8"
            assert kwargs.get("errors") == "replace"


class TestParsing:
    def test_ruff_json_to_finding(self, monkeypatch, tmp_path):
        payload = [{
            "code": "C901",
            "message": "`foo` is too complex (42 > 10)",
            "filename": str(tmp_path / "m.py"),
            "location": {"row": 7, "column": 1},
        }]
        _patch(monkeypatch, ruff_stdout=json.dumps(payload))
        findings = list(PythonChecker().run(tmp_path, _STANDARD))
        cyclo = [f for f in findings if f.rule == "cyclomatic_complexity"]
        assert len(cyclo) == 1
        assert cyclo[0].measured == 42 and cyclo[0].limit == 10
        assert cyclo[0].line == 7
        assert cyclo[0].file == Path("m.py")

    def test_flake8_text_to_finding(self, monkeypatch, tmp_path):
        target = tmp_path / "m.py"
        out = f"{target}:3:1: CCR001 Cognitive complexity is too high (30 > 15)\n"
        _patch(monkeypatch, flake8_stdout=out)
        findings = list(PythonChecker().run(tmp_path, _STANDARD))
        cog = [f for f in findings if f.rule == "cognitive_complexity"]
        assert len(cog) == 1
        assert cog[0].measured == 30 and cog[0].limit == 15
        assert cog[0].line == 3


@pytest.mark.slow
def test_real_ruff_and_flake8_find_complex_function(tmp_path):
    (tmp_path / "complex_mod.py").write_text(_COMPLEX_SOURCE, encoding="utf-8")
    findings = list(PythonChecker().run(tmp_path, _STANDARD))
    assert len(findings) >= 1
    assert all(f.measured > f.limit for f in findings)
