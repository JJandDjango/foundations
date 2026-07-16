"""Error and result classes for prompt validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class ValidationError:
    """A single validation error or warning."""

    line: int
    message: str
    severity: Literal["error", "warning"]

    def __str__(self) -> str:
        return f"  Line {self.line}: {self.message}"


@dataclass
class ValidationResult:
    """Result of validating a prompt file.

    ``passed`` is True when no errors (not warnings) are present. The
    ``token_count`` is filled in by the parser.
    """

    file_path: str
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    token_count: int = 0

    @property
    def passed(self) -> bool:
        return not self.errors

    def add_error(self, line: int, message: str) -> None:
        self.errors.append(ValidationError(line, message, "error"))

    def add_warning(self, line: int, message: str) -> None:
        self.warnings.append(ValidationError(line, message, "warning"))

    def __str__(self) -> str:
        out = [f"Validating: {self.file_path}", ""]
        if self.errors:
            out.append("ERRORS:")
            for err in self.errors:
                out.append(str(err))
            out.append("")
        if self.warnings:
            out.append("WARNINGS:")
            for warn in self.warnings:
                out.append(str(warn))
            out.append("")
        status = "PASS" if self.passed else "FAIL"
        out.append(
            f"Result: {status} ({len(self.errors)} errors, {len(self.warnings)} warnings)"
        )
        return "\n".join(out)
