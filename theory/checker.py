"""Theory verdict computation.

parse_trailer  — extract the first Theory: trailer value (with git folding)
evaluate_substance — length floor + banned-phrase check
evaluate_scope — fnmatch against config scope globs
load_map_components — parse MAP.md frontmatter for component names
check — full six-step algorithm
"""

from __future__ import annotations

import fnmatch
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from theory.config import TheoryConfig


@dataclass
class TheoryVerdict:
    status: str  # "pass" | "warn" | "fail"
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DiffInfo:
    """Diff statistics acquired from git for trivial cross-check and judge."""

    added_lines: "int | None" = None
    deleted_lines: "int | None" = None
    diff_text: "str | None" = None


@dataclass(frozen=True)
class Evidence:
    """Optional acquired context for check(): MAP components, diff stats, judge.

    Everything here is evidence the caller (normally the CLI) gathered before
    the check; each field independently absent degrades that step to a no-op.
    """

    map_components: "list[str] | None" = None
    diff: "DiffInfo | None" = None
    judge: "object | None" = None


def parse_trailer(commit_msg: str) -> str | None:
    """Return the first Theory: trailer value, or None if absent.

    Rules (spec: standards/theory/SPEC.md §3):
    - Matches a line beginning at column 0 with the literal text 'Theory:'
      (case-sensitive).
    - Git trailer continuation lines — lines immediately following a matched
      trailer line that start with one or more spaces — are unfolded: the
      leading whitespace is stripped and the continuation is appended to the
      value with a single space separator.
    - First match wins; subsequent Theory: lines are ignored.
    - Returns the value text (everything after 'Theory: ', stripped of
      leading/trailing whitespace after unfolding).
    """
    lines = commit_msg.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("Theory:"):
            # Extract the value after "Theory:"
            value = line[len("Theory:"):].strip()
            # Unfold continuation lines (start with at least one space)
            j = i + 1
            while j < len(lines) and lines[j].startswith(" "):
                value += " " + lines[j].strip()
                j += 1
            return value
    return None


def evaluate_substance(trailer_value: str, config: TheoryConfig) -> TheoryVerdict:
    """Check substance rules against the trailer value.

    Rules:
    - len(trailer_value.strip()) < config.min_length → fail, reason:
      "Theory: trailer too short (N < min_length chars)"
    - trailer_value.strip().lower() in config.banned_phrases → fail, reason:
      "Theory: trailer is a banned stock phrase: '<phrase>'"
    - Banned-phrase matching is whole-value and case-insensitive.
    - Both rules are evaluated independently; if both fire, both reasons appear.
    Returns TheoryVerdict("pass", []) when neither rule fires.
    """
    stripped = trailer_value.strip()
    reasons: list[str] = []

    if len(stripped) < config.min_length:
        reasons.append(
            f"Theory: trailer too short ({len(stripped)} < {config.min_length} chars)"
        )

    lower_value = stripped.lower()
    banned_lower = [p.lower() for p in config.banned_phrases]
    if lower_value in banned_lower:
        reasons.append(
            f"Theory: trailer is a banned stock phrase: '{lower_value}'"
        )

    if reasons:
        return TheoryVerdict("fail", reasons)
    return TheoryVerdict("pass", [])


def evaluate_scope(changed_files: list[str], scope_globs: list[str]) -> bool:
    """Return True if any changed_file matches any scope_glob.

    Matching: fnmatch.fnmatch on POSIX-normalized path (forward slashes),
    case-insensitive on Windows (sys.platform == 'win32').  Out-of-scope
    commits produce no output; this function only determines scope.
    """
    case_insensitive = sys.platform == "win32"
    for f in changed_files:
        # POSIX-normalize (forward slashes)
        normalized = f.replace("\\", "/")
        for glob in scope_globs:
            if case_insensitive:
                if fnmatch.fnmatch(normalized.lower(), glob.lower()):
                    return True
            else:
                if fnmatch.fnmatch(normalized, glob):
                    return True
    return False


def _parse_frontmatter(content: str) -> "dict | None":
    """Parse a leading '---'-delimited YAML frontmatter block to a dict.

    Returns None when there is no frontmatter or it is not a YAML mapping.
    """
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end == -1:
        return None
    data = yaml.safe_load(content[3:end].strip())
    return data if isinstance(data, dict) else None


def _component_names(components: list) -> list[str]:
    """Extract name strings from frontmatter component entries.

    - dict entry with str 'name' key  → yields the name string
    - dict entry with missing/non-str 'name' key  → skipped silently
    - str entry  → yields the string as-is (backward compatibility)
    - any other type  → skipped silently
    """
    result: list[str] = []
    for c in components:
        if isinstance(c, dict):
            name = c.get("name")
            if isinstance(name, str):
                result.append(name)
        elif isinstance(c, str):
            result.append(c)
    return result


def load_map_components(map_path: "str | Path") -> "list[str] | None":
    """Parse authored component names from MAP.md YAML frontmatter.

    Returns a list of component name strings extracted from the frontmatter
    'components:' key, or None if the file is absent, has no YAML frontmatter
    (delimited by '---' lines), the frontmatter cannot be parsed, or the
    'components:' key is absent. Never raises; all failures degrade to None
    silently.
    """
    try:
        path = Path(map_path)
        if not path.exists():
            return None
        data = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if data is None:
            return None
        components = data.get("components")
        if not isinstance(components, list):
            return None
        return _component_names(components)
    except Exception:
        return None


def _verdict_for_trivial(
    trailer_value: str, config: TheoryConfig, diff: "DiffInfo | None"
) -> "TheoryVerdict | None":
    """Step 3: resolve a 'trivial - <class>' trailer, or None if not trivial-form.

    Unknown class → fail; valid class over the size cross-check → warn;
    valid class otherwise → pass.
    """
    trivial_match = re.match(
        r"^trivial\s*[-–—]\s*(.+)$", trailer_value, re.IGNORECASE
    )
    if not trivial_match:
        return None
    trivial_class = trivial_match.group(1).strip().lower()
    if trivial_class not in [c.lower() for c in config.trivial_classes]:
        return TheoryVerdict("fail", [f"unknown trivial class: '{trivial_class}'"])
    _diff = diff or DiffInfo()
    if (
        config.trivial_max_lines > 0
        and _diff.added_lines is not None
        and _diff.deleted_lines is not None
        and (_diff.added_lines + _diff.deleted_lines) > config.trivial_max_lines
    ):
        total = _diff.added_lines + _diff.deleted_lines
        return TheoryVerdict(
            "warn",
            [
                f"trivial - {trivial_class} claimed but the diff is "
                f"{total} changed lines (> {config.trivial_max_lines})"
            ],
        )
    return TheoryVerdict("pass", [])


def _map_warn(trailer_value: str, map_components: "list[str] | None") -> "str | None":
    """Step 5: MAP reconciliation — warn text when no component is named."""
    if map_components is None:
        return None
    lower_value = trailer_value.lower()
    if any(comp.lower() in lower_value for comp in map_components):
        return None
    return "rationale names no authored MAP component"


def _judge_warn(
    trailer_value: str, changed_files: list[str], evidence: Evidence
) -> "str | None":
    """Step 6: LLM judge — warn text for every verdict except 'explains'."""
    judge, diff = evidence.judge, evidence.diff
    if judge is None or diff is None or diff.diff_text is None:
        return None
    verdict = judge.evaluate(trailer_value, changed_files, diff)
    if verdict.status == "does_not_explain":
        return "judge: rationale does not explain the change" + (
            f": {verdict.reason}" if verdict.reason else ""
        )
    if verdict.status == "unavailable":
        return (
            "judge unavailable"
            + (f" ({verdict.reason})" if verdict.reason else "")
            + "; deterministic bar only"
        )
    if verdict.status == "unparseable":
        return "judge verdict unparseable; deterministic bar only"
    return None  # "explains"


def check(
    commit_msg: str,
    changed_files: list[str],
    config: TheoryConfig,
    evidence: "Evidence | None" = None,
) -> TheoryVerdict:
    """Full theory check.

    Algorithm:
    1. evaluate_scope(changed_files, config.scope) → False →
       return TheoryVerdict("pass", [])           # out-of-scope: silent pass
    2. parse_trailer(commit_msg) → None →
       return TheoryVerdict("fail", ["missing Theory: trailer"])
    3. trivial check (_verdict_for_trivial): fail / warn / pass when trivial-form
    4. evaluate_substance(trailer_value, config) → if status == "fail", return that verdict
    5. MAP reconciliation (_map_warn): miss appends to warns list
    6. Judge step (_judge_warn): appends to warns list
    7. return TheoryVerdict("warn", warns) if warns else TheoryVerdict("pass", [])

    Optional acquired context (MAP components, diff stats, judge) arrives as
    *evidence*; each absent field degrades its step to a no-op.
    """
    _evidence = evidence or Evidence()

    # Step 1: scope check
    if not evaluate_scope(changed_files, config.scope):
        return TheoryVerdict("pass", [])

    # Step 2: trailer check
    trailer_value = parse_trailer(commit_msg)
    if trailer_value is None:
        return TheoryVerdict("fail", ["missing Theory: trailer"])

    # Step 3: trivial check
    trivial = _verdict_for_trivial(trailer_value, config, _evidence.diff)
    if trivial is not None:
        return trivial

    # Step 4: substance check
    substance = evaluate_substance(trailer_value, config)
    if substance.status == "fail":
        return substance

    # Steps 5–6: warn accumulation
    warns = [
        w
        for w in (
            _map_warn(trailer_value, _evidence.map_components),
            _judge_warn(trailer_value, changed_files, _evidence),
        )
        if w is not None
    ]

    # Step 7: return
    return TheoryVerdict("warn", warns) if warns else TheoryVerdict("pass", [])
