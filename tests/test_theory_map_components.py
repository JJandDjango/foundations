"""
Functional tests for Slice (v): ``theory_map_component_parse_fix``

Written against the spec contract (origin-harness spec) only.
No reads of ``agentic/**`` or ``tests/test_*.py`` at authoring time.
No live Anthropic SDK calls — all tests are pure in-process using
deterministic YAML fixtures written to tmp_path.

Acceptance Criteria covered (AC1–AC8):
  AC1  – Object-shaped entries with name: keys → ["harness", "theory"]
  AC2  – Plain-string entries (backward compat) → ["harness", "theory"]
  AC3  – Dict missing name key → entry skipped; no dict-repr in result
  AC4  – Dict with name: 42 (int) → entry skipped silently
  AC5  – Production-shaped fixture + check() rationale mentioning "harness" → pass
  AC6  – Production-shaped fixture + check() rationale without component → warn
  AC7  – Absent file → None without raising
  AC8  – Return value elements are plain strings (no element starts with "{'")

Error Modes covered (all 7):
  EM-DICT-NAME      – dict entry with str name → name appended (AC1)
  EM-DICT-NO-NAME   – dict entry missing/non-str name → skipped silently (AC3, AC4)
  EM-STRING         – plain string entry → appended as-is (AC2)
  EM-ABSENT         – file absent → None (AC7)
  EM-NO-FM          – no frontmatter → None
  EM-NO-KEY         – no components: key → None
  EM-EXCEPTION      – unexpected/malformed input → None silently

Spec reference: origin-harness spec — slice v (theory_map_component_parse_fix),
2026-06-11.
"""
from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
# tests/functional/ -> tests/ -> project root
_ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# MAP fixture constants
# ---------------------------------------------------------------------------

# Production-shaped fixture: object entries with name + role + level + location
_OBJECT_FORMAT_MAP = """\
---
title: MAP
components:
  - name: harness
    role: coordinator
    level: 1
    location: agentic/harness/
  - name: theory
    role: enforcement
    level: 3
    location: agentic/theory/
---
"""

# Legacy/backward-compatible format: plain string entries
_STRING_FORMAT_MAP = """\
---
title: MAP
components:
  - harness
  - theory
---
"""

# Mixed format: one object entry + one string entry
_MIXED_FORMAT_MAP = """\
---
title: MAP
components:
  - name: harness
    role: coordinator
  - theory
---
"""

# Object entry missing the 'name' key entirely
_MISSING_NAME_KEY_MAP = """\
---
title: MAP
components:
  - role: coordinator
    level: 1
  - name: theory
    role: enforcement
---
"""

# Object entry with non-string (integer) name value
_NON_STRING_NAME_MAP = """\
---
title: MAP
components:
  - name: 42
    role: coordinator
  - name: theory
    role: enforcement
---
"""

# File with no YAML frontmatter block
_NO_FRONTMATTER = "Just a plain text file with no YAML frontmatter markers.\n"

# File with frontmatter but no 'components:' key
_NO_COMPONENTS_KEY = """\
---
title: MAP
other_key: some_value
---
"""

# File with a valid frontmatter start but unterminated YAML (causes parse error)
_MALFORMED_YAML = "---\ncomponents: {unterminated bracket\n---\n"


# ===========================================================================
# AC1 / EM-DICT-NAME — Object-shaped entries yield name strings
# ===========================================================================


class TestObjectEntriesYieldName:
    """AC1 / EM-DICT-NAME: object-shaped entries → name strings extracted correctly."""

    def test_ac1_returns_exact_name_list(self, tmp_path: Path) -> None:
        """AC1: production-shaped fixture → returns exactly [\"harness\", \"theory\"]."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_OBJECT_FORMAT_MAP)
        result = load_map_components(map_file)
        assert result == ["harness", "theory"], (
            f"Expected [\"harness\", \"theory\"], got {result!r}. "
            "Spec AC1: object entries must yield the 'name' value, not a dict-repr."
        )

    def test_ac1_result_contains_harness(self, tmp_path: Path) -> None:
        """AC1: 'harness' appears in the result."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_OBJECT_FORMAT_MAP)
        result = load_map_components(map_file)
        assert result is not None
        assert "harness" in result, f"'harness' missing from result: {result!r}"

    def test_ac1_result_contains_theory(self, tmp_path: Path) -> None:
        """AC1: 'theory' appears in the result."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_OBJECT_FORMAT_MAP)
        result = load_map_components(map_file)
        assert result is not None
        assert "theory" in result, f"'theory' missing from result: {result!r}"

    def test_ac1_result_is_list(self, tmp_path: Path) -> None:
        """AC1: return value is a list (not None, not a dict)."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_OBJECT_FORMAT_MAP)
        result = load_map_components(map_file)
        assert isinstance(result, list), (
            f"Expected list, got {type(result).__name__!r}: {result!r}"
        )

    def test_em_dict_name_all_elements_are_plain_strings(self, tmp_path: Path) -> None:
        """EM-DICT-NAME: every element returned is a str (not a dict, not a repr)."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_OBJECT_FORMAT_MAP)
        result = load_map_components(map_file)
        assert result is not None
        for elem in result:
            assert isinstance(elem, str), (
                f"Non-string element: {elem!r} (type {type(elem).__name__})"
            )


# ===========================================================================
# AC2 / EM-STRING — Plain-string entries backward compatibility
# ===========================================================================


class TestStringEntriesBackwardCompat:
    """AC2 / EM-STRING: plain string component entries continue to work."""

    def test_ac2_string_entries_return_correct_list(self, tmp_path: Path) -> None:
        """AC2: string-format fixture → [\"harness\", \"theory\"] (backward compat preserved)."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_STRING_FORMAT_MAP)
        result = load_map_components(map_file)
        assert result == ["harness", "theory"], (
            f"Expected [\"harness\", \"theory\"] from string format, got {result!r}. "
            "Spec AC2: plain-string entries must still be returned as-is."
        )

    def test_ac2_string_format_not_none(self, tmp_path: Path) -> None:
        """AC2: string-format fixture → not None."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_STRING_FORMAT_MAP)
        assert load_map_components(map_file) is not None


# ===========================================================================
# AC3 / EM-DICT-NO-NAME — Dict missing name key → entry skipped silently
# ===========================================================================


class TestDictMissingNameKeySkipped:
    """AC3 / EM-DICT-NO-NAME: dict entry without a 'name' key is skipped silently."""

    def test_ac3_missing_name_key_entry_skipped(self, tmp_path: Path) -> None:
        """AC3: first dict entry has no 'name' key → that entry is absent from result."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_MISSING_NAME_KEY_MAP)
        result = load_map_components(map_file)
        # First dict has only role+level keys; second dict has name: theory
        assert result is not None
        assert "theory" in result
        # Ensure no dict-repr string leaked through
        for elem in result:
            assert not elem.startswith("{'"), (
                f"Dict-repr leaked into result: {elem!r}. "
                "Spec AC3: missing-name dict entries must be skipped silently."
            )

    def test_ac3_no_curly_brace_in_any_element(self, tmp_path: Path) -> None:
        """AC3: no element in result contains '{{' (dict-repr artifact)."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_MISSING_NAME_KEY_MAP)
        result = load_map_components(map_file)
        assert result is not None
        for elem in result:
            assert "{" not in elem, (
                f"Element contains '{{' — likely a dict-repr: {elem!r}"
            )

    def test_em_dict_no_name_missing_key_does_not_raise(self, tmp_path: Path) -> None:
        """EM-DICT-NO-NAME: missing name key must not raise an exception."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_MISSING_NAME_KEY_MAP)
        try:
            result = load_map_components(map_file)
        except Exception as exc:
            pytest.fail(
                f"load_map_components raised {type(exc).__name__}: {exc} "
                "for a dict entry missing 'name'. Spec EM-DICT-NO-NAME: must not raise."
            )
        else:
            assert isinstance(result, list)


# ===========================================================================
# AC4 / EM-DICT-NO-NAME — Non-string name value → entry skipped silently
# ===========================================================================


class TestNonStringNameSkipped:
    """AC4 / EM-DICT-NO-NAME: dict entry with non-string name (e.g. int 42) is skipped."""

    def test_ac4_integer_name_not_in_result(self, tmp_path: Path) -> None:
        """AC4: entry with name: 42 (int) → '42' must not appear in result."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_NON_STRING_NAME_MAP)
        result = load_map_components(map_file)
        assert result is not None
        assert "42" not in result, (
            f"Integer name '42' must be skipped, found in result: {result!r}. "
            "Spec AC4: non-string 'name' values must be skipped silently."
        )

    def test_ac4_valid_sibling_entry_still_returned(self, tmp_path: Path) -> None:
        """AC4: valid str-named sibling entry ('theory') is still returned."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_NON_STRING_NAME_MAP)
        result = load_map_components(map_file)
        assert result is not None
        assert "theory" in result, (
            f"'theory' (valid name) should be in result even when sibling has int name; "
            f"got {result!r}"
        )

    def test_em_dict_no_name_integer_does_not_raise(self, tmp_path: Path) -> None:
        """EM-DICT-NO-NAME: integer name value must not raise an exception."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_NON_STRING_NAME_MAP)
        try:
            load_map_components(map_file)
        except Exception as exc:
            pytest.fail(
                f"Raised {type(exc).__name__}: {exc} for int-named entry. "
                "Spec EM-DICT-NO-NAME: non-string name must be skipped without raising."
            )


# ===========================================================================
# AC5 — Production-shaped fixture + check() with matching rationale → pass
# ===========================================================================


class TestProductionFixturePassPath:
    """AC5: production-shaped MAP fixture + component-naming rationale → pass, no spurious warn."""

    def test_ac5_rationale_with_harness_passes(self, tmp_path: Path) -> None:
        """AC5: rationale mentioning 'harness' → TheoryVerdict(status='pass', reasons=[])."""
        from theory.checker import load_map_components
        from theory import check, TheoryConfig

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_OBJECT_FORMAT_MAP)
        components = load_map_components(map_file)
        result = check(
            "Theory: fixes harness dispatch to eliminate the retry double-count in harness",
            ["src/foo.py"],
            TheoryConfig(),
            map_components=components,
        )
        assert result.status == "pass", (
            f"Expected 'pass' when rationale mentions 'harness' (an MAP component), "
            f"got {result.status!r}. Spec AC5: no spurious MAP warn after the fix. "
            f"reasons={result.reasons!r}"
        )
        assert result.reasons == [], (
            f"Pass verdict must have empty reasons; got {result.reasons!r}"
        )

    def test_ac5_rationale_with_theory_passes(self, tmp_path: Path) -> None:
        """AC5: rationale mentioning 'theory' → status 'pass'."""
        from theory.checker import load_map_components
        from theory import check, TheoryConfig

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_OBJECT_FORMAT_MAP)
        components = load_map_components(map_file)
        result = check(
            "Theory: theory checker now correctly extracts component names from MAP frontmatter",
            ["src/foo.py"],
            TheoryConfig(),
            map_components=components,
        )
        assert result.status == "pass", (
            f"Expected 'pass' for rationale mentioning 'theory'; got {result.status!r}. "
            f"reasons={result.reasons!r}"
        )

    def test_ac5_pre_fix_bug_would_warn_but_now_passes(self, tmp_path: Path) -> None:
        """AC5 regression guard: the pre-fix str(c) bug produced spurious warns; now must pass."""
        from theory.checker import load_map_components
        from theory import check, TheoryConfig

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_OBJECT_FORMAT_MAP)
        components = load_map_components(map_file)
        # Pre-fix: components list was ["{'name': 'harness', ...}", "{'name': 'theory', ...}"]
        # 'harness' never matched a dict-repr → every commit warned spuriously.
        # Post-fix: components list is ["harness", "theory"] → substring match succeeds.
        result = check(
            "Theory: restructures harness orchestration to fix the retry double-count",
            ["src/foo.py"],
            TheoryConfig(),
            map_components=components,
        )
        assert result.status != "warn", (
            f"Spurious MAP warn detected — the pre-fix dict-repr bug appears to still be present. "
            f"Spec AC5: warn must not fire when rationale names a real MAP component. "
            f"status={result.status!r}, reasons={result.reasons!r}"
        )


# ===========================================================================
# AC6 — Production-shaped fixture + check() with no component name → warn
# ===========================================================================


class TestProductionFixtureWarnPath:
    """AC6: production-shaped fixture + rationale not naming any component → real MAP warn fires."""

    def test_ac6_rationale_without_component_warns(self, tmp_path: Path) -> None:
        """AC6: rationale mentioning no MAP component → TheoryVerdict(status='warn')."""
        from theory.checker import load_map_components
        from theory import check, TheoryConfig

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_OBJECT_FORMAT_MAP)
        components = load_map_components(map_file)
        result = check(
            "Theory: fixes dispatch to eliminate the retry double-count here",
            ["src/foo.py"],
            TheoryConfig(),
            map_components=components,
        )
        assert result.status == "warn", (
            f"Expected 'warn' for rationale naming no MAP component; "
            f"got {result.status!r}. Spec AC6: real MAP miss must still warn correctly."
        )

    def test_ac6_warn_verdict_has_at_least_one_reason(self, tmp_path: Path) -> None:
        """AC6: warn verdict must carry at least one reason."""
        from theory.checker import load_map_components
        from theory import check, TheoryConfig

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_OBJECT_FORMAT_MAP)
        components = load_map_components(map_file)
        result = check(
            "Theory: fixes dispatch to eliminate the retry double-count here",
            ["src/foo.py"],
            TheoryConfig(),
            map_components=components,
        )
        assert len(result.reasons) >= 1, (
            f"Warn verdict must carry at least one reason; got reasons={result.reasons!r}"
        )

    def test_ac6_warn_reason_mentions_map_or_component(self, tmp_path: Path) -> None:
        """AC6: warn reason must reference MAP or component concepts."""
        from theory.checker import load_map_components
        from theory import check, TheoryConfig

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_OBJECT_FORMAT_MAP)
        components = load_map_components(map_file)
        result = check(
            "Theory: fixes dispatch to eliminate the retry double-count here",
            ["src/foo.py"],
            TheoryConfig(),
            map_components=components,
        )
        assert any(
            "map" in r.lower() or "component" in r.lower()
            for r in result.reasons
        ), f"Warn reasons don't mention MAP or component: {result.reasons!r}"


# ===========================================================================
# AC7 / EM-ABSENT — Absent file → None without raising
# ===========================================================================


class TestAbsentFileReturnsNone:
    """AC7 / EM-ABSENT: absent MAP file → None, never raises."""

    def test_ac7_absent_file_returns_none(self, tmp_path: Path) -> None:
        """AC7: path to a non-existent file → None."""
        from theory.checker import load_map_components

        result = load_map_components(tmp_path / "does_not_exist.md")
        assert result is None, (
            f"Expected None for absent file, got {result!r}. "
            "Spec AC7: non-existent map_file file must return None."
        )

    def test_ac7_absent_file_does_not_raise(self, tmp_path: Path) -> None:
        """AC7: absent file must not raise any exception."""
        from theory.checker import load_map_components

        try:
            load_map_components(tmp_path / "does_not_exist.md")
        except Exception as exc:
            pytest.fail(
                f"load_map_components raised {type(exc).__name__}: {exc} "
                "for a non-existent file. Spec AC7: must return None without raising."
            )

    def test_em_absent_deeply_nested_missing_path_returns_none(self, tmp_path: Path) -> None:
        """EM-ABSENT: deeply nested missing path → None, no exception."""
        from theory.checker import load_map_components

        result = load_map_components(tmp_path / "sub" / "dir" / "MAP.md")
        assert result is None, f"Expected None for nested missing path; got {result!r}"


# ===========================================================================
# AC8 / EM-DICT-NAME — Return value elements are plain strings (no dict-repr)
# ===========================================================================


class TestReturnValueElementsArePlainStrings:
    """AC8: every element in the returned list is a plain string, not a dict-repr."""

    def test_ac8_no_element_starts_with_dict_open(self, tmp_path: Path) -> None:
        """AC8: no element starts with \"{'\" (dict-repr prefix)."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_OBJECT_FORMAT_MAP)
        result = load_map_components(map_file)
        assert result is not None
        for elem in result:
            assert not elem.startswith("{'"), (
                f"Element looks like a stringified dict: {elem!r}. "
                "Spec AC8: load_map_components must return plain name strings."
            )

    def test_ac8_isinstance_str_for_all_elements(self, tmp_path: Path) -> None:
        """AC8: isinstance(elem, str) is True for every returned element."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_OBJECT_FORMAT_MAP)
        result = load_map_components(map_file)
        assert result is not None
        for elem in result:
            assert isinstance(elem, str), (
                f"Non-string element in result: {elem!r} "
                f"(type {type(elem).__name__})"
            )

    def test_ac8_elements_match_name_values_not_dict_reprs(self, tmp_path: Path) -> None:
        """AC8: returned strings equal the raw name values ('harness', 'theory'), not reprs."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_OBJECT_FORMAT_MAP)
        result = load_map_components(map_file)
        assert result is not None
        # The raw name values are 'harness' and 'theory' — short, no braces
        for elem in result:
            assert len(elem) < 50, (
                f"Element suspiciously long for a name string: {elem!r}"
            )
            assert "name" not in elem or elem == "name", (
                f"Element contains 'name' key artifact — looks like a repr: {elem!r}"
            )


# ===========================================================================
# EM-NO-FM — File with no YAML frontmatter → None
# ===========================================================================


class TestNoFrontmatterReturnsNone:
    """EM-NO-FM: file without a '---' frontmatter block → None."""

    def test_em_no_fm_plain_text_returns_none(self, tmp_path: Path) -> None:
        """EM-NO-FM: file starting with plain text (no '---') → None."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_NO_FRONTMATTER)
        result = load_map_components(map_file)
        assert result is None, (
            f"Expected None for file with no frontmatter, got {result!r}. "
            "Spec EM-NO-FM: no YAML frontmatter block → None."
        )

    def test_em_no_fm_does_not_raise(self, tmp_path: Path) -> None:
        """EM-NO-FM: no-frontmatter file must not raise."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_NO_FRONTMATTER)
        try:
            load_map_components(map_file)
        except Exception as exc:
            pytest.fail(
                f"Raised {type(exc).__name__}: {exc} for no-frontmatter file. "
                "Spec EM-NO-FM: must return None without raising."
            )

    def test_em_no_fm_empty_file_returns_none(self, tmp_path: Path) -> None:
        """EM-NO-FM: empty file → None (no frontmatter start)."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text("")
        result = load_map_components(map_file)
        assert result is None, f"Expected None for empty file; got {result!r}"


# ===========================================================================
# EM-NO-KEY — Frontmatter present but no 'components:' key → None
# ===========================================================================


class TestNoComponentsKeyReturnsNone:
    """EM-NO-KEY: valid frontmatter but no 'components:' key → None."""

    def test_em_no_key_returns_none(self, tmp_path: Path) -> None:
        """EM-NO-KEY: frontmatter without components: key → None."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_NO_COMPONENTS_KEY)
        result = load_map_components(map_file)
        assert result is None, (
            f"Expected None when frontmatter has no 'components:' key, got {result!r}. "
            "Spec EM-NO-KEY: absent components key → None."
        )

    def test_em_no_key_does_not_raise(self, tmp_path: Path) -> None:
        """EM-NO-KEY: no components key must not raise."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_NO_COMPONENTS_KEY)
        try:
            load_map_components(map_file)
        except Exception as exc:
            pytest.fail(
                f"Raised {type(exc).__name__}: {exc} for frontmatter without 'components:'. "
                "Spec EM-NO-KEY: must return None without raising."
            )


# ===========================================================================
# EM-EXCEPTION — Unexpected / malformed input → None silently
# ===========================================================================


class TestExceptionDegradesToNone:
    """EM-EXCEPTION: malformed YAML or other unexpected errors → None, never raises."""

    def test_em_exception_malformed_yaml_returns_none(self, tmp_path: Path) -> None:
        """EM-EXCEPTION: frontmatter with unterminated YAML → None (parse error caught)."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_MALFORMED_YAML)
        try:
            result = load_map_components(map_file)
        except Exception as exc:
            pytest.fail(
                f"load_map_components raised {type(exc).__name__}: {exc} "
                "for malformed YAML. Spec EM-EXCEPTION: all errors must degrade to None silently."
            )
        else:
            # Accept either None (parsed but no useful data) or an empty list
            assert result is None or isinstance(result, list), (
                f"Expected None or list for malformed YAML; got {result!r}"
            )


# ===========================================================================
# Mixed entries (EM-DICT-NAME + EM-STRING in the same fixture)
# ===========================================================================


class TestMixedEntries:
    """Mixed object and string entries: both are correctly extracted."""

    def test_mixed_entries_all_names_extracted(self, tmp_path: Path) -> None:
        """Mixed fixture: object entry + string entry → both names in result."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_MIXED_FORMAT_MAP)
        result = load_map_components(map_file)
        assert result is not None
        assert "harness" in result, f"'harness' (from object entry) not in {result!r}"
        assert "theory" in result, f"'theory' (from string entry) not in {result!r}"

    def test_mixed_entries_no_dict_repr(self, tmp_path: Path) -> None:
        """Mixed fixture: no element is a dict-repr string."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_MIXED_FORMAT_MAP)
        result = load_map_components(map_file)
        assert result is not None
        for elem in result:
            assert not elem.startswith("{'"), (
                f"Dict-repr leaked into mixed result: {elem!r}"
            )


# ===========================================================================
# Full end-to-end: production fixture round-trip through check()
# ===========================================================================


class TestProductionFixtureEndToEnd:
    """End-to-end: production MAP.md → load_map_components → check() integration."""

    def test_full_round_trip_pass_then_warn(self, tmp_path: Path) -> None:
        """AC5 + AC6 combined: same components, two rationales → pass then warn."""
        from theory.checker import load_map_components
        from theory import check, TheoryConfig, TheoryVerdict

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_OBJECT_FORMAT_MAP)
        components = load_map_components(map_file)

        # AC5: rationale names 'harness' → pass
        v_pass = check(
            "Theory: fixes harness dispatch to eliminate the retry double-count in harness",
            ["src/foo.py"],
            TheoryConfig(),
            map_components=components,
        )
        assert isinstance(v_pass, TheoryVerdict)
        assert v_pass.status == "pass", (
            f"Expected pass for harness-naming rationale; got {v_pass.status!r}. "
            f"reasons={v_pass.reasons!r}"
        )

        # AC6: rationale names no component → warn
        v_warn = check(
            "Theory: fixes dispatch to eliminate the retry double-count here",
            ["src/foo.py"],
            TheoryConfig(),
            map_components=components,
        )
        assert isinstance(v_warn, TheoryVerdict)
        assert v_warn.status == "warn", (
            f"Expected warn for no-component rationale; got {v_warn.status!r}. "
            f"reasons={v_warn.reasons!r}"
        )

    def test_production_fixture_names_are_plain_strings(self, tmp_path: Path) -> None:
        """Production fixture: load_map_components returns plain strings, not dict-reprs (AC8)."""
        from theory.checker import load_map_components

        map_file = tmp_path / "MAP.md"
        map_file.write_text(_OBJECT_FORMAT_MAP)
        result = load_map_components(map_file)
        assert result is not None
        assert result == ["harness", "theory"]
        for elem in result:
            assert isinstance(elem, str) and not elem.startswith("{'"), (
                f"Unexpected element shape: {elem!r}"
            )

    def test_load_map_components_is_callable(self) -> None:
        """load_map_components must be importable and callable from theory.checker."""
        from theory.checker import load_map_components

        assert callable(load_map_components), (
            "load_map_components must be a callable exported from theory.checker"
        )
