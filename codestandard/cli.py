"""CLI entry point for ``python -m codestandard <project_root>``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from codestandard.checks.python_checker import PythonChecker
from codestandard.core import CodeChecker
from codestandard.standard import load_standard


def _build_checker() -> CodeChecker:
    """Build the default checker with all standard checks registered."""
    return CodeChecker(checks=[PythonChecker()])


def main(argv: list[str] | None = None) -> int:
    """Run the code-standard engine.

    Usage:
        python -m codestandard <project_root> [--standard <path>]

    Returns:
        Exit code: 0 = no findings, 1 = one or more findings, or a load/parse/
        subprocess error.
    """
    parser = argparse.ArgumentParser(
        prog="python -m codestandard",
        description="Measure Python source against the house code standard.",
    )
    parser.add_argument("project_root", help="Path to the project to check.")
    parser.add_argument(
        "--standard",
        default=None,
        help="Alternate standard YAML (default: packaged code_standard.yaml).",
    )
    args = parser.parse_args(argv)

    try:
        standard = load_standard(Path(args.standard) if args.standard else None)
    except FileNotFoundError as exc:
        print(f"ERROR  standard not found: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR  invalid standard: {exc}", file=sys.stderr)
        return 1

    checker = _build_checker()
    try:
        findings = checker.run(Path(args.project_root), standard)
    except RuntimeError as exc:
        print(f"ERROR  {exc}", file=sys.stderr)
        return 1

    for finding in findings:
        print(str(finding))

    return 1 if findings else 0
