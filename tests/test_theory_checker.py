"""Tests for :mod:`theory.checker`.

Covers acceptance criteria AC3–AC14 in full:
- parse_trailer: present, absent, unfolded continuation, first-match, column-0
- evaluate_substance: banned phrase, too short, both, valid, case-insensitive
- evaluate_scope: in-scope glob match, out-of-scope, exact match, multiple globs
- check end-to-end: all eight cases from the spec
"""

from __future__ import annotations

import pytest

from theory.checker import (
    Evidence,
    DiffInfo,
    TheoryVerdict,
    check,
    evaluate_scope,
    evaluate_substance,
    load_map_components,
    parse_trailer,
)
from theory.config import TheoryConfig
from theory.judge import JudgeVerdict


# ---------------------------------------------------------------------------
# parse_trailer
# ---------------------------------------------------------------------------


class TestParseTrailer:
    """parse_trailer extraction (AC3, AC4, AC5)."""

    def test_present_returns_value(self) -> None:
        """AC3: returns value after 'Theory: ' stripped."""
        result = parse_trailer("Theory: why this matters\nOther: line")
        assert result == "why this matters"

    def test_absent_returns_none(self) -> None:
        """AC4: no Theory: line → None."""
        result = parse_trailer("no Theory trailer here")
        assert result is None

    def test_unfolded_continuation(self) -> None:
        """AC5: continuation line (leading space) is unfolded with a space."""
        result = parse_trailer("Theory: first line\n  continuation here")
        assert result == "first line continuation here"

    def test_first_match_wins(self) -> None:
        result = parse_trailer("Theory: first\nTheory: second")
        assert result == "first"

    def test_not_column_zero_not_matched(self) -> None:
        """Theory: not at column 0 is not a trailer."""
        result = parse_trailer(" Theory: not at column 0\nOther: line")
        assert result is None

    def test_empty_message_returns_none(self) -> None:
        result = parse_trailer("")
        assert result is None

    def test_stripped_leading_trailing_whitespace(self) -> None:
        result = parse_trailer("Theory:   spaced value  ")
        assert result == "spaced value"

    def test_value_after_non_theory_lines(self) -> None:
        result = parse_trailer("Subject: some commit\n\nBody.\n\nTheory: the real reason")
        assert result == "the real reason"


# ---------------------------------------------------------------------------
# evaluate_substance
# ---------------------------------------------------------------------------


class TestEvaluateSubstance:
    """Substance checks: length floor + banned phrase."""

    def test_banned_phrase_fails(self) -> None:
        verdict = evaluate_substance("fix", TheoryConfig())
        assert verdict.status == "fail"
        assert any("banned" in r for r in verdict.reasons)

    def test_too_short_fails(self) -> None:
        verdict = evaluate_substance("ok", TheoryConfig())
        assert verdict.status == "fail"
        assert any("too short" in r for r in verdict.reasons)

    def test_both_banned_and_short_both_reasons_present(self) -> None:
        """'fix' is both banned AND short → two reasons."""
        verdict = evaluate_substance("fix", TheoryConfig())
        assert verdict.status == "fail"
        assert len(verdict.reasons) == 2
        assert any("too short" in r for r in verdict.reasons)
        assert any("banned" in r for r in verdict.reasons)

    def test_valid_substance_passes(self) -> None:
        verdict = evaluate_substance(
            "separates state tracking from step dispatch in the walker", TheoryConfig()
        )
        assert verdict.status == "pass"
        assert verdict.reasons == []

    def test_banned_phrase_case_insensitive_upper(self) -> None:
        verdict = evaluate_substance("FIX", TheoryConfig())
        assert verdict.status == "fail"
        assert any("banned" in r for r in verdict.reasons)

    def test_banned_phrase_case_insensitive_mixed(self) -> None:
        verdict = evaluate_substance("Fixes", TheoryConfig())
        assert verdict.status == "fail"
        assert any("banned" in r for r in verdict.reasons)

    def test_banned_phrase_substring_not_banned(self) -> None:
        """A value that CONTAINS a banned phrase but is not EQUAL to it passes."""
        # "fixes the retry" is not equal to "fixes" → not banned
        verdict = evaluate_substance("fixes the retry double-count in the walker", TheoryConfig())
        # long enough, not a whole-value match → pass
        assert verdict.status == "pass"

    def test_length_reason_format(self) -> None:
        verdict = evaluate_substance("hi", TheoryConfig())
        assert any("2 < 20 chars" in r for r in verdict.reasons)


# ---------------------------------------------------------------------------
# evaluate_scope
# ---------------------------------------------------------------------------


class TestEvaluateScope:
    """Scope glob matching."""

    def test_in_scope_glob_match(self) -> None:
        assert evaluate_scope(["src/foo.py"], ["src/**"]) is True

    def test_out_of_scope_returns_false(self) -> None:
        assert evaluate_scope(["unrelated/path.txt"], ["agentic/**"]) is False

    def test_exact_file_match(self) -> None:
        assert evaluate_scope(["orchestrate.py"], ["orchestrate.py"]) is True

    def test_multiple_globs_any_match(self) -> None:
        assert evaluate_scope(["tests/foo.py"], ["agentic/**", "tests/**"]) is True

    def test_empty_files_returns_false(self) -> None:
        assert evaluate_scope([], ["agentic/**"]) is False

    def test_empty_globs_returns_false(self) -> None:
        assert evaluate_scope(["src/foo.py"], []) is False

    def test_nested_path_matches_double_star(self) -> None:
        assert evaluate_scope(["agentic/sub/deep/file.py"], ["agentic/**"]) is True

    def test_agentic_dir_in_default_scope(self) -> None:
        config = TheoryConfig()
        assert evaluate_scope(["agentic/harness/walker.py"], config.scope) is True


# ---------------------------------------------------------------------------
# check — end-to-end (AC6–AC14)
# ---------------------------------------------------------------------------


class TestCheckEndToEnd:
    """check() end-to-end: all eight canonical cases from the spec."""

    def test_banned_phrase_fails(self) -> None:
        """AC6: 'fixes' is banned and short → fail."""
        verdict = check("Theory: fixes", ["src/foo.py"], TheoryConfig())
        assert verdict.status == "fail"

    def test_valid_rationale_passes(self) -> None:
        """AC7: long non-banned rationale → pass."""
        verdict = check(
            "Theory: separates state tracking from step dispatch to fix the retry double-count",
            ["src/foo.py"],
            TheoryConfig(),
        )
        assert verdict.status == "pass"
        assert verdict.reasons == []

    def test_trivial_valid_class_passes(self) -> None:
        """AC8: trivial-rename → pass."""
        verdict = check(
            "Theory: trivial - rename", ["src/foo.py"], TheoryConfig()
        )
        assert verdict.status == "pass"
        assert verdict.reasons == []

    def test_trivial_unknown_class_fails(self) -> None:
        """AC9: trivial-unknownclass → fail with reason containing the class."""
        verdict = check(
            "Theory: trivial - unknownclass", ["src/foo.py"], TheoryConfig()
        )
        assert verdict.status == "fail"
        assert any("unknownclass" in r for r in verdict.reasons)

    def test_out_of_scope_with_trailer_passes_silently(self) -> None:
        """AC10: out-of-scope even with trailer → pass (no EM1 fired).

        The packaged default scope is ["**"] (everything in scope), so
        out-of-scope semantics are exercised with a narrowed repo config.
        """
        verdict = check(
            "Theory: why this matters",
            ["unrelated/path.txt"],
            TheoryConfig(scope=["src/**"]),
        )
        assert verdict.status == "pass"
        assert verdict.reasons == []

    def test_out_of_scope_without_trailer_passes_silently(self) -> None:
        """AC11: out-of-scope without trailer → pass (EM1 NOT fired)."""
        verdict = check(
            "no trailer", ["unrelated/path.txt"], TheoryConfig(scope=["src/**"])
        )
        assert verdict.status == "pass"
        assert verdict.reasons == []

    def test_in_scope_missing_trailer_fails(self) -> None:
        """AC12: in-scope, missing trailer → EM1."""
        verdict = check("no trailer", ["src/foo.py"], TheoryConfig())
        assert verdict.status == "fail"
        assert verdict.reasons == ["missing Theory: trailer"]

    def test_map_component_case_insensitive_match_passes(self) -> None:
        """AC13: 'walker' in rationale matches component 'Walker' → pass."""
        verdict = check(
            "Theory: explains the design tradeoff in the walker state machine",
            ["src/foo.py"],
            TheoryConfig(),
            evidence=Evidence(
                map_components=["Walker", "Harness"],
            ),
        )
        assert verdict.status == "pass"
        assert verdict.reasons == []

    def test_map_no_component_match_warns(self) -> None:
        """AC14: valid rationale but no MAP component mentioned → warn."""
        verdict = check(
            "Theory: explains the design tradeoff in the state machine",
            ["src/foo.py"],
            TheoryConfig(),
            evidence=Evidence(
                map_components=["Walker", "Harness"],
            ),
        )
        assert verdict.status == "warn"

    def test_map_none_no_warn(self) -> None:
        """No MAP components supplied → no MAP warn, straight pass."""
        verdict = check(
            "Theory: explains the design tradeoff in the state machine",
            ["src/foo.py"],
            TheoryConfig(),
            evidence=Evidence(
                map_components=None,
            ),
        )
        assert verdict.status == "pass"

    def test_scope_check_before_trailer_check(self) -> None:
        """Scope is evaluated first; out-of-scope → silent pass even without trailer."""
        verdict = check(
            "no trailer at all",
            ["completely/unrelated/file.js"],
            TheoryConfig(scope=["src/**"]),
        )
        assert verdict.status == "pass"

    def test_trivial_with_em_dash_separator(self) -> None:
        """All three trivial separators work: -, –, —."""
        verdict = check(
            "Theory: trivial — rename", ["src/foo.py"], TheoryConfig()
        )
        assert verdict.status == "pass"

    def test_trivial_with_en_dash_separator(self) -> None:
        verdict = check(
            "Theory: trivial – formatting", ["src/foo.py"], TheoryConfig()
        )
        assert verdict.status == "pass"


# ---------------------------------------------------------------------------
# load_map_components
# ---------------------------------------------------------------------------


class TestLoadMapComponents:
    """Tests for load_map_components covering object entries, string entries,
    edge cases, and the production-shaped MAP fixture (AC1–AC8)."""

    # -- AC1: object entries yield name value ---------------------------------

    def test_object_entries_yield_name(self, tmp_path) -> None:
        """AC1: object entries with name: key → plain name strings returned."""
        map_file = tmp_path / "MAP.md"
        map_file.write_text(
            "---\ntitle: MAP\ncomponents:\n"
            "  - name: harness\n    role: coordinator\n"
            "  - name: theory\n    role: enforcement\n---\n",
            encoding="utf-8",
        )
        result = load_map_components(map_file)
        assert result == ["harness", "theory"]

    # -- AC2: string entries backward compatibility ----------------------------

    def test_string_entries_backward_compat(self, tmp_path) -> None:
        """AC2: plain-string component entries still work (backward compat)."""
        map_file = tmp_path / "MAP.md"
        map_file.write_text(
            "---\ncomponents:\n  - harness\n  - theory\n---\n",
            encoding="utf-8",
        )
        result = load_map_components(map_file)
        assert result == ["harness", "theory"]

    # -- AC3 (mixed context): one object + one string -------------------------

    def test_mixed_entries_both_extracted(self, tmp_path) -> None:
        """Mixed entries (object + string) → both names returned."""
        map_file = tmp_path / "MAP.md"
        map_file.write_text(
            "---\ncomponents:\n  - name: harness\n    role: coordinator\n"
            "  - theory\n---\n",
            encoding="utf-8",
        )
        result = load_map_components(map_file)
        assert result == ["harness", "theory"]

    # -- AC3 (dict missing name): silently skipped ----------------------------

    def test_object_missing_name_key_skipped(self, tmp_path) -> None:
        """AC3: dict entry with no 'name' key is silently skipped."""
        map_file = tmp_path / "MAP.md"
        map_file.write_text(
            "---\ncomponents:\n  - role: coordinator\n  - name: theory\n---\n",
            encoding="utf-8",
        )
        result = load_map_components(map_file)
        assert result == ["theory"]

    # -- AC4: non-string name skipped -----------------------------------------

    def test_object_nonstring_name_skipped(self, tmp_path) -> None:
        """AC4: dict entry with name: 42 (int) → entry skipped."""
        map_file = tmp_path / "MAP.md"
        map_file.write_text(
            "---\ncomponents:\n  - name: 42\n  - name: theory\n---\n",
            encoding="utf-8",
        )
        result = load_map_components(map_file)
        assert result == ["theory"]

    # -- AC7: absent file returns None ----------------------------------------

    def test_absent_file_returns_none(self, tmp_path) -> None:
        """AC7: nonexistent path → None without raising."""
        result = load_map_components(tmp_path / "nonexistent.md")
        assert result is None

    # -- no frontmatter → None ------------------------------------------------

    def test_no_frontmatter_returns_none(self, tmp_path) -> None:
        """File without '---' frontmatter delimiter → None."""
        map_file = tmp_path / "MAP.md"
        map_file.write_text("# Just a plain markdown file\nNo frontmatter here.\n", encoding="utf-8")
        result = load_map_components(map_file)
        assert result is None

    # -- no components: key → None --------------------------------------------

    def test_components_key_absent_returns_none(self, tmp_path) -> None:
        """Frontmatter present but 'components:' key absent → None."""
        map_file = tmp_path / "MAP.md"
        map_file.write_text(
            "---\ntitle: MAP\nauthor: test\n---\n# Content\n",
            encoding="utf-8",
        )
        result = load_map_components(map_file)
        assert result is None

    # -- AC1/AC8: full production fixture -------------------------------------

    def test_full_production_fixture_end_to_end(self, tmp_path) -> None:
        """AC1+AC8: production-shaped MAP.md returns plain name strings."""
        map_file = tmp_path / "MAP.md"
        map_file.write_text(
            "---\n"
            "title: MAP\n"
            "components:\n"
            "  - name: harness\n"
            "    role: coordinator\n"
            "    level: 1\n"
            "    location: agentic/harness/\n"
            "  - name: theory\n"
            "    role: enforcement\n"
            "    level: 3\n"
            "    location: agentic/theory/\n"
            "---\n",
            encoding="utf-8",
        )
        result = load_map_components(map_file)
        assert result == ["harness", "theory"]
        # AC8: no element should be a dict repr
        assert all(not r.startswith("{'") for r in result)


# ---------------------------------------------------------------------------
# T9: TestTrivialityCheck — trivial cross-check (ACs 22-25)
# ---------------------------------------------------------------------------

# Valid message for in-scope commit (long enough, no banned phrase)
_VALID_MSG = "Theory: separates state tracking from step dispatch in the walker"
_IN_SCOPE = ["src/foo.py"]


class TestTrivialityCheck:
    """Trivial size cross-check (ACs 22-25)."""

    def test_ac22_over_limit_returns_warn(self) -> None:
        """AC22: sum=120 > 100 -> warn containing class name, total, and limit."""
        config = TheoryConfig()  # trivial_max_lines=100
        verdict = check(
            "Theory: trivial - rename",
            _IN_SCOPE,
            config,
            evidence=Evidence(
                diff=DiffInfo(added_lines=60, deleted_lines=60),
            ),
        )
        assert verdict.status == "warn"
        assert len(verdict.reasons) == 1
        msg = verdict.reasons[0]
        assert "rename" in msg
        assert "120" in msg
        assert "100" in msg

    def test_ac23_under_limit_returns_pass(self) -> None:
        """AC23: sum=80 <= 100 -> pass."""
        config = TheoryConfig()  # trivial_max_lines=100
        verdict = check(
            "Theory: trivial - rename",
            _IN_SCOPE,
            config,
            evidence=Evidence(
                diff=DiffInfo(added_lines=40, deleted_lines=40),
            ),
        )
        assert verdict.status == "pass"
        assert verdict.reasons == []

    def test_ac24_disabled_trivial_max_lines_zero(self) -> None:
        """AC24 (EM-TRIVIAL-DISABLED): trivial_max_lines=0 -> no cross-check -> pass."""
        config = TheoryConfig(trivial_max_lines=0)
        verdict = check(
            "Theory: trivial - rename",
            _IN_SCOPE,
            config,
            evidence=Evidence(
                diff=DiffInfo(added_lines=500, deleted_lines=500),
            ),
        )
        assert verdict.status == "pass"
        assert verdict.reasons == []

    def test_ac25_none_counts_skips_cross_check(self) -> None:
        """AC25 (EM-NUMSTAT-GIT-FAIL): None counts -> cross-check skipped -> pass."""
        config = TheoryConfig()  # trivial_max_lines=100
        verdict = check(
            "Theory: trivial - rename",
            _IN_SCOPE,
            config,
            evidence=Evidence(
                diff=DiffInfo(),  # all None
            ),
        )
        assert verdict.status == "pass"
        assert verdict.reasons == []

    def test_trivial_no_diff_arg_skips_cross_check(self) -> None:
        """diff=None -> DiffInfo() used internally -> counts None -> pass."""
        config = TheoryConfig()  # trivial_max_lines=100
        verdict = check(
            "Theory: trivial - rename",
            _IN_SCOPE,
            config,
        )
        assert verdict.status == "pass"

    def test_trivial_exactly_at_limit_passes(self) -> None:
        """Sum exactly equal to trivial_max_lines (100) -> pass (not over)."""
        config = TheoryConfig()  # trivial_max_lines=100
        verdict = check(
            "Theory: trivial - rename",
            _IN_SCOPE,
            config,
            evidence=Evidence(
                diff=DiffInfo(added_lines=50, deleted_lines=50),
            ),
        )
        assert verdict.status == "pass"


# ---------------------------------------------------------------------------
# T9: FakeJudge helper for warn accumulation tests
# ---------------------------------------------------------------------------


class FakeJudge:
    """Minimal judge stub for testing check() warn accumulation."""

    def __init__(self, verdict: JudgeVerdict) -> None:
        self._verdict = verdict
        self.call_count = 0

    def evaluate(
        self, rationale: str, changed_files: "list[str]", diff: DiffInfo
    ) -> JudgeVerdict:
        self.call_count += 1
        return self._verdict


# ---------------------------------------------------------------------------
# T9: TestWarnAccumulation — multi-warn accumulation (ACs 26-32)
# ---------------------------------------------------------------------------


class TestWarnAccumulation:
    """check() warn accumulation: MAP miss + judge disagrees (ACs 26-32)."""

    def test_ac26_map_miss_plus_judge_disagrees_two_warns(self) -> None:
        """AC26: MAP miss + judge disagrees -> warn with 2 reasons."""
        judge = FakeJudge(JudgeVerdict("does_not_explain", "rationale is vague"))
        # Use components not mentioned in _VALID_MSG to guarantee an MAP miss
        verdict = check(
            _VALID_MSG,
            _IN_SCOPE,
            TheoryConfig(),
            evidence=Evidence(
                map_components=["Harness"],  # "harness" not in _VALID_MSG -> MAP miss
                judge=judge,
                diff=DiffInfo(diff_text="some diff"),
            ),
        )
        assert verdict.status == "warn"
        assert len(verdict.reasons) == 2

    def test_ac27_map_miss_only_one_warn(self) -> None:
        """AC27: MAP miss, no judge -> warn with 1 reason."""
        verdict = check(
            _VALID_MSG,
            _IN_SCOPE,
            TheoryConfig(),
            evidence=Evidence(
                map_components=["Harness"],  # "harness" not in _VALID_MSG -> MAP miss
                judge=None,
            ),
        )
        assert verdict.status == "warn"
        assert len(verdict.reasons) == 1

    def test_ac28_judge_unavailable_warn_contains_unavailable(self) -> None:
        """AC28: judge unavailable -> reasons contain 'unavailable'."""
        judge = FakeJudge(JudgeVerdict("unavailable", "connection refused"))
        verdict = check(
            _VALID_MSG,
            _IN_SCOPE,
            TheoryConfig(),
            evidence=Evidence(
                judge=judge,
                diff=DiffInfo(diff_text="some diff"),
            ),
        )
        assert verdict.status == "warn"
        assert any("unavailable" in r for r in verdict.reasons)

    def test_ac29_judge_unparseable_warn_contains_unparseable(self) -> None:
        """AC29: judge unparseable -> reasons contain 'unparseable'."""
        judge = FakeJudge(JudgeVerdict("unparseable", None))
        verdict = check(
            _VALID_MSG,
            _IN_SCOPE,
            TheoryConfig(),
            evidence=Evidence(
                judge=judge,
                diff=DiffInfo(diff_text="some diff"),
            ),
        )
        assert verdict.status == "warn"
        assert any("unparseable" in r for r in verdict.reasons)

    def test_ac30_map_match_plus_judge_agrees_pass(self) -> None:
        """AC30: MAP match + judge agrees -> pass."""
        judge = FakeJudge(JudgeVerdict("explains", "clear"))
        verdict = check(
            "Theory: extends harness state machine to support parallel spawns",
            _IN_SCOPE,
            TheoryConfig(),
            evidence=Evidence(
                map_components=["Harness"],
                judge=judge,
                diff=DiffInfo(diff_text="some diff"),
            ),
        )
        assert verdict.status == "pass"

    def test_ac31_diff_text_none_judge_not_called(self) -> None:
        """AC31: diff_text absent -> judge not called -> pass (no other warns)."""
        judge = FakeJudge(JudgeVerdict("does_not_explain", "vague"))
        verdict = check(
            _VALID_MSG,
            _IN_SCOPE,
            TheoryConfig(),
            evidence=Evidence(
                judge=judge,
                diff=DiffInfo(diff_text=None),
            ),
        )
        assert verdict.status == "pass"
        assert judge.call_count == 0

    def test_ac32_diff_none_judge_not_called(self) -> None:
        """AC32: diff=None -> judge not called."""
        judge = FakeJudge(JudgeVerdict("does_not_explain", "vague"))
        verdict = check(
            _VALID_MSG,
            _IN_SCOPE,
            TheoryConfig(),
            evidence=Evidence(
                judge=judge,
                diff=None,
            ),
        )
        assert verdict.status == "pass"
        assert judge.call_count == 0


# ---------------------------------------------------------------------------
# T9: TestJudgeSkipConditions — judge not called on early returns (ACs 33-34)
# ---------------------------------------------------------------------------


class TestJudgeSkipConditions:
    """Judge is not called when check() returns early (ACs 33-34)."""

    def test_ac33_substance_fail_judge_not_called(self) -> None:
        """AC33: banned phrase -> substance FAIL before judge step -> judge not called."""
        judge = FakeJudge(JudgeVerdict("does_not_explain", "vague"))
        verdict = check(
            "Theory: fix",  # banned phrase -> FAIL
            _IN_SCOPE,
            TheoryConfig(),
            evidence=Evidence(
                judge=judge,
                diff=DiffInfo(diff_text="some diff"),
            ),
        )
        assert verdict.status == "fail"
        assert judge.call_count == 0

    def test_ac34_valid_trivial_judge_not_called(self) -> None:
        """AC34: valid trivial (under limit) -> returns before judge -> judge not called."""
        judge = FakeJudge(JudgeVerdict("does_not_explain", "vague"))
        verdict = check(
            "Theory: trivial - rename",
            _IN_SCOPE,
            TheoryConfig(),
            evidence=Evidence(
                judge=judge,
                diff=DiffInfo(added_lines=10, deleted_lines=10, diff_text="some diff"),
            ),
        )
        assert verdict.status == "pass"
        assert judge.call_count == 0
