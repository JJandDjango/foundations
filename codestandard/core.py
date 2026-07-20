"""Core code-standard primitives: CodeFinding, CodeCheck protocol, CodeChecker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable


@dataclass(frozen=True)
class CodeFinding:
    """A single code-standard violation."""

    rule: str
    """Rule name as it appears in the standard, e.g. ``"cognitive_complexity"``."""

    file: Path
    """Project-relative path to the file containing the violation."""

    line: int
    """1-based line number of the violation."""

    measured: int
    """Measured value (e.g. cognitive complexity = 42)."""

    limit: int
    """Resolved limit from the standard (e.g. 15)."""

    message: str
    """Human-readable description, e.g. ``"`foo` is too complex (42 > 15)"``."""

    def __str__(self) -> str:
        """Format: ``"<rule>  <file>:<line>  <measured>/<limit>  <message>"``.

        The file is rendered POSIX-style (forward slashes) so output is stable
        across platforms.
        """
        return (
            f"{self.rule}  {self.file.as_posix()}:{self.line}  "
            f"{self.measured}/{self.limit}  {self.message}"
        )


@runtime_checkable
class CodeCheck(Protocol):
    """Protocol that all code checks must satisfy."""

    rule: str
    """Rule name this check enforces."""

    def run(
        self,
        project_root: Path,
        standard: dict,
    ) -> Iterable[CodeFinding]:
        """Yield findings for all violations of this rule under *project_root*."""
        ...


class CodeChecker:
    """Runs a collection of :class:`CodeCheck` instances and aggregates results."""

    def __init__(self, checks: list[CodeCheck]) -> None:
        self._checks = checks

    def run(self, project_root: Path, standard: dict) -> list[CodeFinding]:
        """Run all checks; return findings sorted by ``(file, line, rule)``.

        The sort makes output deterministic across runs.
        """
        findings: list[CodeFinding] = []
        for check in self._checks:
            findings.extend(check.run(project_root, standard))
        findings.sort(key=lambda f: (f.file.as_posix(), f.line, f.rule))
        return findings
