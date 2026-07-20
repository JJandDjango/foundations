"""PythonChecker — measure Python source via ruff + flake8-cognitive-complexity.

Shells the pinned tools (ruff 0.15.17, flake8 7.3.0 + flake8-cognitive-complexity
0.1.0 — the ``foundations[codestandard]`` extra) as subprocesses, decodes their
output UTF-8/replace, and translates findings into :class:`CodeFinding`
instances against the resolved house standard.

``PLR0912`` (branches) is deliberately NOT selected: branching is gated by
cognitive + cyclomatic + nesting per the ratified five principles, so branch-count
is not a separate engine rule. ``nesting_depth`` has no clean ruff code yet and is
skipped with a note in v0.0.1.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from codestandard.core import CodeFinding


# ruff diagnostic code -> house rule name.
_RUFF_CODE_TO_RULE = {
    "C901": "cyclomatic_complexity",
    "PLR0911": "returns",
    "PLR0913": "params",
    "PLR0915": "function_length",
}

# --select value passed to ruff — derived from the map, so it can never drift to
# include PLR0912.
_RUFF_SELECT = ",".join(_RUFF_CODE_TO_RULE)

# Pulls "(<measured> > <limit>)" out of a ruff/flake8 message.
_MEASURE_RE = re.compile(r"\((\d+)\s*>\s*(\d+)\)")

# flake8 text line: "<path>:<row>:<col>: CCR001 <message ...>".
_FLAKE8_LINE_RE = re.compile(
    r"^(?P<path>.+?):(?P<row>\d+):(?P<col>\d+):\s+(?P<msg>CCR001\b.*)$"
)


def _resolved_max(standard: dict, rule: str, default: int) -> int:
    """Return the ``max`` limit for *rule* from *standard*, or *default*."""
    entry = standard.get("rules", {}).get(rule, {})
    return int(entry.get("max", default))


def _run_tool(cmd: list[str], root: Path) -> subprocess.CompletedProcess:
    """Run *cmd* under *root*, decoding stdout/stderr UTF-8/replace.

    A missing tool (OSError) is surfaced as a RuntimeError the CLI reports.
    """
    try:
        return subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(f"checker failed: {cmd[0]}  {exc}") from exc


class PythonChecker:
    """Python code checker: ruff (C901/PLR0911/PLR0913/PLR0915) + flake8 (CCR001)."""

    rule = "python"

    def run(self, project_root: Path, standard: dict) -> Iterable[CodeFinding]:
        root = Path(project_root).resolve()
        self._note_unenforced(standard)
        findings: list[CodeFinding] = []
        findings.extend(self._run_ruff(root, standard))
        findings.extend(self._run_flake8(root, standard))
        return findings

    def _run_ruff(self, root: Path, standard: dict) -> list[CodeFinding]:
        cmd = [
            "ruff", "check", str(root),
            "--select", _RUFF_SELECT,
            "--output-format", "json",
            "--config", f"lint.mccabe.max-complexity={_resolved_max(standard, 'cyclomatic_complexity', 10)}",
            "--config", f"lint.pylint.max-args={_resolved_max(standard, 'params', 5)}",
            "--config", f"lint.pylint.max-returns={_resolved_max(standard, 'returns', 6)}",
            "--config", f"lint.pylint.max-statements={_resolved_max(standard, 'function_length', 50)}",
        ]
        proc = _run_tool(cmd, root)
        if proc.returncode not in (0, 1):
            raise RuntimeError(f"checker failed: ruff  {proc.stderr.strip()}")
        text = proc.stdout.strip()
        if not text:
            return []
        try:
            items = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"checker failed: ruff  unparseable output: {exc}") from exc
        findings: list[CodeFinding] = []
        for item in items:
            rule = _RUFF_CODE_TO_RULE.get(item.get("code"))
            if rule is None:
                continue
            finding = self._finding_from_message(
                rule=rule,
                message=item.get("message", ""),
                filename=item.get("filename", ""),
                row=item.get("location", {}).get("row", 0),
                root=root,
            )
            if finding is not None:
                findings.append(finding)
        return findings

    def _run_flake8(self, root: Path, standard: dict) -> list[CodeFinding]:
        cmd = [
            "flake8", str(root),
            "--select=CCR001",
            f"--max-cognitive-complexity={_resolved_max(standard, 'cognitive_complexity', 15)}",
        ]
        proc = _run_tool(cmd, root)
        if proc.returncode not in (0, 1):
            raise RuntimeError(f"checker failed: flake8  {proc.stderr.strip()}")
        findings: list[CodeFinding] = []
        for line in proc.stdout.splitlines():
            match = _FLAKE8_LINE_RE.match(line)
            if match is None:
                continue
            finding = self._finding_from_message(
                rule="cognitive_complexity",
                message=match.group("msg"),
                filename=match.group("path"),
                row=match.group("row"),
                root=root,
            )
            if finding is not None:
                findings.append(finding)
        return findings

    def _finding_from_message(
        self, *, rule: str, message: str, filename: str, row, root: Path
    ) -> CodeFinding | None:
        """Build a finding by parsing ``(measured > limit)`` from *message*."""
        measure = _MEASURE_RE.search(message)
        if measure is None:
            return None
        return CodeFinding(
            rule=rule,
            file=self._relativize(filename, root),
            line=int(row),
            measured=int(measure.group(1)),
            limit=int(measure.group(2)),
            message=message,
        )

    @staticmethod
    def _relativize(filename: str, root: Path) -> Path:
        """Normalize an absolute tool path to project-relative (best-effort)."""
        candidate = Path(filename)
        try:
            return candidate.resolve().relative_to(root)
        except ValueError:
            return candidate

    @staticmethod
    def _note_unenforced(standard: dict) -> None:
        """Emit a single stderr note for rules present but not enforced in v0.0.1."""
        if "nesting_depth" in standard.get("rules", {}):
            print("nesting_depth: not enforced in v0.0.1", file=sys.stderr)
