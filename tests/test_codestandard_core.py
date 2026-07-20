"""Tests for core code-standard primitives (CodeFinding, CodeChecker)."""

from __future__ import annotations

from pathlib import Path

from codestandard.core import CodeChecker, CodeFinding


class _StubCheck:
    rule = "stub"

    def __init__(self, findings):
        self._findings = findings
        self.calls = 0

    def run(self, project_root, standard):
        self.calls += 1
        return list(self._findings)


class TestCodeFinding:
    def test_str_format(self):
        finding = CodeFinding(
            rule="params",
            file=Path("src/x.py"),
            line=12,
            measured=6,
            limit=5,
            message="Too many arguments (6 > 5)",
        )
        assert str(finding) == "params  src/x.py:12  6/5  Too many arguments (6 > 5)"


class TestCodeChecker:
    def test_run_sorts_by_file_line_rule(self):
        f_b5 = CodeFinding(rule="returns", file=Path("b.py"), line=5, measured=7, limit=6, message="m")
        f_a9 = CodeFinding(rule="params", file=Path("a.py"), line=9, measured=6, limit=5, message="m")
        f_a2 = CodeFinding(rule="cyclomatic_complexity", file=Path("a.py"), line=2, measured=12, limit=10, message="m")
        out = CodeChecker([_StubCheck([f_b5, f_a9, f_a2])]).run(Path("."), {})
        assert out == [f_a2, f_a9, f_b5]

    def test_run_calls_each_check_once(self):
        c1, c2 = _StubCheck([]), _StubCheck([])
        CodeChecker([c1, c2]).run(Path("."), {})
        assert c1.calls == 1 and c2.calls == 1
