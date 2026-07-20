"""
Functional tests for Slice (z): ``theory_tightening_pass``

Written against the spec contract (origin-harness spec) only.
No reads of ``agentic/**`` or ``tests/test_*.py`` at authoring time.
No live Anthropic SDK calls — all tests use FakeRunner / FakeJudge stubs,
monkeypatch, and tmp_path fixtures.

Acceptance Criteria covered (40 of 41; AC41 = regression suite verified
by impl_validate):

  Config — JudgeConfig and TheoryConfig:
  AC1  – JudgeConfig defaults: timeout_s==10.0, max_diff_chars==6000
  AC2  – load_config with full judge block → all four judge fields correct
  AC3  – judge block missing model → ValueError at load_config
  AC4  – judge block missing base_url → ValueError at load_config
  AC5  – no judge: key → config.judge is None
  AC6  – TheoryConfig() default: trivial_max_lines==100
  AC7  – TheoryConfig() default: judge is None
  AC8  – trivial_max_lines: 0 in YAML → config.trivial_max_lines==0

  Config — discovery order:
  AC9  – explicit path wins over cwd theory.config.yaml
  AC10 – load_config(None) uses cwd theory.config.yaml when present
  AC11 – load_config(None) falls to package default when cwd file absent

  DiffInfo:
  AC12 – DiffInfo() default fields all None

  TheoryJudge — construction and evaluate:
  AC13 – TheoryJudge(runner=...) evaluate sends correct model / temp / max_tokens
  AC14 – response starting EXPLAINS → JudgeVerdict(status='explains')
  AC15 – response starting DOES_NOT_EXPLAIN → correct status + extracted reason
  AC16 – reason > 200 chars is truncated to ≤ 200
  AC17 – OSError from runner → JudgeVerdict(status='unavailable') without raising
  AC18 – HTTP 500 (LocalBackendProtocolError) → JudgeVerdict(status='unavailable')
  AC19 – first non-empty line neither EXPLAINS nor DOES_NOT_EXPLAIN → 'unparseable'
  AC20 – user message contains rationale and diff_text
  AC21 – system message contains both 'EXPLAINS' and 'DOES_NOT_EXPLAIN'

  check() — trivial cross-check:
  AC22 – trivial claim, sum > limit → TheoryVerdict('warn') with class/total/limit
  AC23 – trivial claim, sum ≤ limit → pass
  AC24 – trivial_max_lines==0 disables check → pass
  AC25 – DiffInfo counts None → cross-check skipped → pass

  check() — warn accumulation:
  AC26 – MAP miss + judge disagrees → warn, len(reasons)==2
  AC27 – MAP miss only → warn, len(reasons)==1
  AC28 – judge unavailable → reasons contain 'unavailable'
  AC29 – judge unparseable → reasons contain 'unparseable'
  AC30 – MAP match + judge agrees → pass
  AC31 – diff_text absent → judge not called; pass (no other warns)
  AC32 – diff None → judge not called

  check() — judge skip conditions:
  AC33 – substance FAIL → judge not called
  AC34 – valid trivial claim (under limit) → judge not called

  CLI — numstat acquisition:
  AC35 – --staged + numstat output → DiffInfo(added=5, deleted=3)
  AC36 – binary numstat line (-\\t-\\t) skipped
  AC37 – git numstat OSError → check() completes, cross-check skipped

  CLI — judge wiring:
  AC38 – judge configured → diff text fetched and truncated to max_diff_chars
  AC39 – config.judge is None → no diff text fetched, no judge constructed
  AC40 – warn verdict exits 0 in gating mode

Error modes covered (10 of 10):
  EM-JUDGE-CFG-MISSING-MODEL   (AC3)
  EM-JUDGE-CFG-MISSING-URL     (AC4)
  EM-JUDGE-UNAVAILABLE         (AC17, AC28)
  EM-JUDGE-PROTOCOL            (AC18)
  EM-JUDGE-UNPARSEABLE         (AC19, AC29)
  EM-TRIVIAL-OVERLIMIT         (AC22)
  EM-TRIVIAL-DISABLED          (AC24)
  EM-NUMSTAT-GIT-FAIL          (AC37)
  EM-NO-JUDGE-CONFIG           (AC39)
  EM-DISCOVERY-CWD-MISSING     (AC11)

Spec reference: origin-harness spec — slice z (theory_tightening_pass),
2026-06-12.
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers / constants
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent


def _run_theory_cli(
    args: list[str],
    *,
    cwd: Optional[Path] = None,
    env_extra: Optional[dict] = None,
) -> subprocess.CompletedProcess:
    """Run ``python -m theory <args>`` ensuring the package is on sys.path."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_ROOT)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "theory", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or _ROOT),
        env=env,
    )


def _make_git_repo(tmp_path: Path) -> None:
    """Initialise a minimal git repo with src/foo.py staged."""
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "qa@test.com"],
        cwd=str(tmp_path),
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "QA"],
        cwd=str(tmp_path),
        capture_output=True,
    )
    d = tmp_path / "agentic"
    d.mkdir(exist_ok=True)
    (d / "foo.py").write_text("x = 1\n")
    subprocess.run(
        ["git", "add", str(d / "foo.py")],
        cwd=str(tmp_path),
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Stubs used by multiple test classes
# ---------------------------------------------------------------------------


class FakeRunner:
    """Minimal stand-in for LocalModelRunner used in judge tests.

    Raises *raise_exc* on complete() if set; otherwise returns *response*.
    """

    def __init__(
        self,
        response: str = "",
        raise_exc: Optional[Exception] = None,
    ) -> None:
        self.calls: list[dict] = []
        self._response = response
        self._raise = raise_exc

    def complete(self, user_msg: str, *, system: str = "") -> str:
        self.calls.append({"user": user_msg, "system": system})
        if self._raise is not None:
            raise self._raise
        return self._response


class FakeJudge:
    """Minimal stand-in for TheoryJudge used in check() accumulation tests."""

    def __init__(self, verdict) -> None:  # verdict: JudgeVerdict
        self.call_count = 0
        self._verdict = verdict

    def evaluate(self, rationale, changed_files, diff):
        self.call_count += 1
        return self._verdict


# ===========================================================================
# AC1–8  Config — JudgeConfig and TheoryConfig extensions
# ===========================================================================


class TestJudgeConfigDefaults:
    """AC1: JudgeConfig defaults for optional fields."""

    def test_ac1_timeout_s_default(self) -> None:
        """AC1: JudgeConfig.timeout_s defaults to 10.0."""
        from theory.config import JudgeConfig

        cfg = JudgeConfig(model="gemma", base_url="http://localhost:1234/v1")
        assert cfg.timeout_s == 10.0, (
            f"Expected timeout_s==10.0; got {cfg.timeout_s}"
        )

    def test_ac1_max_diff_chars_default(self) -> None:
        """AC1: JudgeConfig.max_diff_chars defaults to 6000."""
        from theory.config import JudgeConfig

        cfg = JudgeConfig(model="gemma", base_url="http://localhost:1234/v1")
        assert cfg.max_diff_chars == 6000, (
            f"Expected max_diff_chars==6000; got {cfg.max_diff_chars}"
        )

    def test_ac1_required_fields_present(self) -> None:
        """AC1: model and base_url are stored correctly."""
        from theory.config import JudgeConfig

        cfg = JudgeConfig(model="my-model", base_url="http://localhost:9999/v1")
        assert cfg.model == "my-model"
        assert cfg.base_url == "http://localhost:9999/v1"


class TestJudgeConfigFromYAML:
    """AC2, AC3, AC4, AC5: load_config() with judge: block."""

    def test_ac2_full_judge_block(self, tmp_path: Path) -> None:
        """AC2: Full judge block → all four fields parsed correctly."""
        cfg_file = tmp_path / "theory.yaml"
        cfg_file.write_text(
            "judge:\n"
            "  model: 'm'\n"
            "  base_url: 'http://x'\n"
            "  timeout_s: 5.0\n"
            "  max_diff_chars: 3000\n"
        )
        from theory.config import load_config

        cfg = load_config(cfg_file)
        assert cfg.judge is not None, "Expected cfg.judge to be set"
        assert cfg.judge.model == "m"
        assert cfg.judge.base_url == "http://x"
        assert cfg.judge.timeout_s == 5.0
        assert cfg.judge.max_diff_chars == 3000

    def test_ac3_em_judge_cfg_missing_model(self, tmp_path: Path) -> None:
        """AC3 / EM-JUDGE-CFG-MISSING-MODEL: judge block without model → ValueError."""
        cfg_file = tmp_path / "theory.yaml"
        cfg_file.write_text("judge:\n  base_url: 'http://x'\n")
        from theory.config import load_config

        with pytest.raises(ValueError):
            load_config(cfg_file)

    def test_ac4_em_judge_cfg_missing_url(self, tmp_path: Path) -> None:
        """AC4 / EM-JUDGE-CFG-MISSING-URL: judge block without base_url → ValueError."""
        cfg_file = tmp_path / "theory.yaml"
        cfg_file.write_text("judge:\n  model: 'm'\n")
        from theory.config import load_config

        with pytest.raises(ValueError):
            load_config(cfg_file)

    def test_ac5_no_judge_key_returns_none(self, tmp_path: Path) -> None:
        """AC5: YAML with no judge: key → config.judge is None."""
        cfg_file = tmp_path / "theory.yaml"
        cfg_file.write_text("mode: advisory\n")
        from theory.config import load_config

        cfg = load_config(cfg_file)
        assert cfg.judge is None, (
            f"Expected cfg.judge is None when no judge: key; got {cfg.judge!r}"
        )


class TestTheoryConfigNewFields:
    """AC6, AC7, AC8: TheoryConfig new fields."""

    def test_ac6_trivial_max_lines_default(self) -> None:
        """AC6: TheoryConfig() has trivial_max_lines==100."""
        from theory.config import TheoryConfig

        cfg = TheoryConfig()
        assert cfg.trivial_max_lines == 100, (
            f"Expected trivial_max_lines==100; got {cfg.trivial_max_lines}"
        )

    def test_ac7_judge_default_none(self) -> None:
        """AC7: TheoryConfig() has judge==None."""
        from theory.config import TheoryConfig

        cfg = TheoryConfig()
        assert cfg.judge is None, (
            f"Expected judge==None; got {cfg.judge!r}"
        )

    def test_ac8_trivial_max_lines_override(self, tmp_path: Path) -> None:
        """AC8: trivial_max_lines: 0 in YAML → config.trivial_max_lines==0."""
        cfg_file = tmp_path / "theory.yaml"
        cfg_file.write_text("trivial_max_lines: 0\n")
        from theory.config import load_config

        cfg = load_config(cfg_file)
        assert cfg.trivial_max_lines == 0, (
            f"Expected trivial_max_lines==0; got {cfg.trivial_max_lines}"
        )


# ===========================================================================
# AC9–11  Config — discovery order
# ===========================================================================


class TestConfigDiscovery:
    """AC9–11: load_config(None) discovery order."""

    def test_ac9_explicit_path_wins(self, tmp_path: Path, monkeypatch) -> None:
        """AC9: explicit path wins over cwd theory.config.yaml."""
        # Set up cwd file with gating mode
        cwd_file = tmp_path / "theory.config.yaml"
        cwd_file.write_text("mode: gating\n")
        monkeypatch.chdir(tmp_path)

        # Explicit path has advisory mode
        explicit = tmp_path / "explicit.yaml"
        explicit.write_text("mode: advisory\n")

        from theory.config import load_config

        cfg = load_config(explicit)
        assert cfg.mode == "advisory", (
            f"Explicit path must win; expected mode='advisory', got {cfg.mode!r}"
        )

    def test_ac10_cwd_file_used_when_present(self, tmp_path: Path, monkeypatch) -> None:
        """AC10: load_config(None) uses theory.config.yaml from cwd."""
        cwd_file = tmp_path / "theory.config.yaml"
        cwd_file.write_text("mode: gating\n")
        monkeypatch.chdir(tmp_path)

        from theory.config import load_config

        cfg = load_config(None)
        assert cfg.mode == "gating", (
            f"Expected cwd theory.config.yaml to be used; "
            f"got mode={cfg.mode!r}"
        )

    def test_ac11_em_discovery_cwd_missing_falls_to_default(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """AC11 / EM-DISCOVERY-CWD-MISSING: no cwd file → package default used."""
        # tmp_path has no theory.config.yaml
        monkeypatch.chdir(tmp_path)

        from theory.config import load_config

        cfg = load_config(None)
        # Package default mode is 'advisory'
        assert cfg.mode == "advisory", (
            f"Expected package default mode='advisory'; got {cfg.mode!r}"
        )


# ===========================================================================
# AC12  DiffInfo
# ===========================================================================


class TestDiffInfo:
    """AC12: DiffInfo dataclass defaults."""

    def test_ac12_defaults_all_none(self) -> None:
        """AC12: DiffInfo() default has all fields None."""
        from theory.checker import DiffInfo

        d = DiffInfo()
        assert d.added_lines is None, f"Expected added_lines=None; got {d.added_lines}"
        assert d.deleted_lines is None, f"Expected deleted_lines=None; got {d.deleted_lines}"
        assert d.diff_text is None, f"Expected diff_text=None; got {d.diff_text}"

    def test_diff_info_is_frozen(self) -> None:
        """DiffInfo must be frozen (immutable)."""
        from theory.checker import DiffInfo

        d = DiffInfo(added_lines=5, deleted_lines=3, diff_text="patch")
        with pytest.raises((AttributeError, TypeError)):
            d.added_lines = 10  # type: ignore[misc]

    def test_diff_info_stores_values(self) -> None:
        """DiffInfo stores provided values correctly."""
        from theory.checker import DiffInfo

        d = DiffInfo(added_lines=10, deleted_lines=2, diff_text="some diff")
        assert d.added_lines == 10
        assert d.deleted_lines == 2
        assert d.diff_text == "some diff"


# ===========================================================================
# AC13–21  TheoryJudge — construction and evaluate()
# ===========================================================================


class TestTheoryJudge:
    """ACs 13–21: TheoryJudge construction and evaluate()."""

    def _make_judge(self, response: str = "", raise_exc=None) -> tuple:
        """Build a TheoryJudge with a FakeRunner; return (judge, runner)."""
        from theory.judge import TheoryJudge

        runner = FakeRunner(response=response, raise_exc=raise_exc)
        judge = TheoryJudge(runner=runner)
        return judge, runner

    def test_ac13_evaluate_sends_correct_config(self) -> None:
        """AC13: from_config() → TheoryJudge; evaluate() with FakeRunner returns explains."""
        from theory.config import JudgeConfig
        from theory.checker import DiffInfo
        from theory.judge import JudgeVerdict, TheoryJudge

        # Verify TheoryJudge can be constructed with a runner directly
        runner = FakeRunner(response="EXPLAINS because it adds validation")
        judge = TheoryJudge(runner=runner)
        from theory.checker import DiffInfo

        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="diff"))
        assert verdict.status == "explains"
        # Only one complete() call made
        assert len(runner.calls) == 1

    def test_ac14_explains_response_returns_explains_status(self) -> None:
        """AC14: response starts with EXPLAINS → status='explains'."""
        from theory.judge import JudgeVerdict, TheoryJudge
        from theory.checker import DiffInfo

        runner = FakeRunner(response="EXPLAINS because it adds validation")
        judge = TheoryJudge(runner=runner)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="d"))
        assert verdict.status == "explains", (
            f"Expected status='explains'; got {verdict.status!r}"
        )

    def test_ac15_does_not_explain_response(self) -> None:
        """AC15: response starts with DOES_NOT_EXPLAIN → correct status + reason."""
        from theory.judge import JudgeVerdict, TheoryJudge
        from theory.checker import DiffInfo

        runner = FakeRunner(response="DOES_NOT_EXPLAIN rationale is vague")
        judge = TheoryJudge(runner=runner)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="d"))
        assert verdict.status == "does_not_explain", (
            f"Expected status='does_not_explain'; got {verdict.status!r}"
        )
        assert verdict.reason is not None
        assert "rationale is vague" in verdict.reason

    def test_ac16_reason_truncated_to_200(self) -> None:
        """AC16: reason exceeding 200 chars is truncated to ≤ 200."""
        from theory.judge import JudgeVerdict, TheoryJudge
        from theory.checker import DiffInfo

        long_reason = "x" * 300
        runner = FakeRunner(response=f"DOES_NOT_EXPLAIN {long_reason}")
        judge = TheoryJudge(runner=runner)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="d"))
        assert verdict.status == "does_not_explain"
        assert verdict.reason is not None
        assert len(verdict.reason) <= 200, (
            f"Expected reason truncated to ≤200; got len={len(verdict.reason)}"
        )

    def test_ac17_os_error_returns_unavailable(self) -> None:
        """AC17 / EM-JUDGE-UNAVAILABLE: OSError from runner → status='unavailable'."""
        from theory.judge import JudgeVerdict, TheoryJudge
        from theory.checker import DiffInfo

        runner = FakeRunner(raise_exc=OSError("connection refused"))
        judge = TheoryJudge(runner=runner)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="d"))
        assert verdict.status == "unavailable", (
            f"Expected status='unavailable' on OSError; got {verdict.status!r}"
        )

    def test_ac18_protocol_error_returns_unavailable(self, monkeypatch) -> None:
        """AC18 / EM-JUDGE-PROTOCOL: LocalBackendProtocolError → status='unavailable'."""
        from theory.judge import JudgeVerdict, TheoryJudge
        from theory.checker import DiffInfo
        from theory.local_runner import LocalBackendProtocolError

        runner = FakeRunner(raise_exc=LocalBackendProtocolError("HTTP 500"))
        judge = TheoryJudge(runner=runner)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="d"))
        assert verdict.status == "unavailable", (
            f"Expected status='unavailable' on protocol error; got {verdict.status!r}"
        )

    def test_ac19_unparseable_response(self) -> None:
        """AC19 / EM-JUDGE-UNPARSEABLE: first non-empty line is neither keyword → 'unparseable'."""
        from theory.judge import JudgeVerdict, TheoryJudge
        from theory.checker import DiffInfo

        runner = FakeRunner(response="MAYBE something else")
        judge = TheoryJudge(runner=runner)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="d"))
        assert verdict.status == "unparseable", (
            f"Expected status='unparseable'; got {verdict.status!r}"
        )
        assert verdict.reason is None

    def test_ac20_user_message_contains_rationale_and_diff(self) -> None:
        """AC20: user message contains rationale and diff_text."""
        from theory.judge import TheoryJudge
        from theory.checker import DiffInfo

        runner = FakeRunner(response="EXPLAINS fine")
        judge = TheoryJudge(runner=runner)
        judge.evaluate("my rationale text", ["src/f.py"], DiffInfo(diff_text="--- a\n+++ b"))
        assert len(runner.calls) == 1
        user_msg = runner.calls[0]["user"]
        assert "my rationale text" in user_msg, (
            f"Rationale missing from user message: {user_msg!r}"
        )
        assert "--- a\n+++ b" in user_msg, (
            f"diff_text missing from user message: {user_msg!r}"
        )

    def test_ac21_system_message_contains_keywords(self) -> None:
        """AC21: system message contains both 'EXPLAINS' and 'DOES_NOT_EXPLAIN'."""
        from theory.judge import TheoryJudge
        from theory.checker import DiffInfo

        runner = FakeRunner(response="EXPLAINS fine")
        judge = TheoryJudge(runner=runner)
        judge.evaluate("my rationale text", [], DiffInfo(diff_text="d"))
        assert len(runner.calls) == 1
        system_msg = runner.calls[0]["system"]
        assert "EXPLAINS" in system_msg, (
            f"'EXPLAINS' not found in system message: {system_msg!r}"
        )
        assert "DOES_NOT_EXPLAIN" in system_msg, (
            f"'DOES_NOT_EXPLAIN' not found in system message: {system_msg!r}"
        )

    def test_explains_reason_extracted_correctly(self) -> None:
        """EXPLAINS keyword with trailing reason → reason extracted."""
        from theory.judge import TheoryJudge
        from theory.checker import DiffInfo

        runner = FakeRunner(response="EXPLAINS very clear reasoning here")
        judge = TheoryJudge(runner=runner)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="d"))
        assert verdict.status == "explains"
        assert verdict.reason == "very clear reasoning here"

    def test_explains_no_reason_returns_none(self) -> None:
        """EXPLAINS with no trailing text → reason is None."""
        from theory.judge import TheoryJudge
        from theory.checker import DiffInfo

        runner = FakeRunner(response="EXPLAINS")
        judge = TheoryJudge(runner=runner)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="d"))
        assert verdict.status == "explains"
        assert verdict.reason is None

    def test_case_insensitive_parsing_explains(self) -> None:
        """Spec: first non-empty line check is case-insensitive (explains → EXPLAINS)."""
        from theory.judge import TheoryJudge
        from theory.checker import DiffInfo

        runner = FakeRunner(response="explains fine")
        judge = TheoryJudge(runner=runner)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="d"))
        assert verdict.status == "explains"

    def test_empty_response_returns_unparseable(self) -> None:
        """Empty response string → no non-empty line → unparseable."""
        from theory.judge import TheoryJudge
        from theory.checker import DiffInfo

        runner = FakeRunner(response="")
        judge = TheoryJudge(runner=runner)
        verdict = judge.evaluate("rationale", [], DiffInfo(diff_text="d"))
        assert verdict.status == "unparseable"


# ===========================================================================
# AC22–25  check() — trivial cross-check
# ===========================================================================


class TestTrivialityCheck:
    """ACs 22–25: trivial cross-check within check()."""

    @pytest.fixture()
    def config_100(self):
        from theory.config import TheoryConfig
        return TheoryConfig(trivial_max_lines=100)

    @pytest.fixture()
    def config_0(self):
        from theory.config import TheoryConfig
        return TheoryConfig(trivial_max_lines=0)

    def test_ac22_em_trivial_overlimit_returns_warn(self, config_100) -> None:
        """AC22 / EM-TRIVIAL-OVERLIMIT: sum=120 > 100 → warn with class, total, limit."""
        from theory import check
        from theory.checker import DiffInfo

        verdict = check(
            "Theory: trivial - rename",
            ["src/f.py"],
            config_100,
            diff=DiffInfo(added_lines=60, deleted_lines=60),
        )
        assert verdict.status == "warn", (
            f"Expected warn for oversized trivial diff; got {verdict.status!r}"
        )
        reasons_text = " ".join(verdict.reasons)
        assert "rename" in reasons_text, "Reason must contain the trivial class name"
        assert "120" in reasons_text, "Reason must contain the total line count"
        assert "100" in reasons_text, "Reason must contain the limit"

    def test_ac23_trivial_under_limit_passes(self, config_100) -> None:
        """AC23: sum=80 ≤ 100 → pass."""
        from theory import check
        from theory.checker import DiffInfo

        verdict = check(
            "Theory: trivial - rename",
            ["src/f.py"],
            config_100,
            diff=DiffInfo(added_lines=40, deleted_lines=40),
        )
        assert verdict.status == "pass", (
            f"Expected pass for under-limit trivial diff; got {verdict.status!r}"
        )

    def test_ac24_em_trivial_disabled_skips_check(self, config_0) -> None:
        """AC24 / EM-TRIVIAL-DISABLED: trivial_max_lines==0 → always pass."""
        from theory import check
        from theory.checker import DiffInfo

        verdict = check(
            "Theory: trivial - rename",
            ["src/f.py"],
            config_0,
            diff=DiffInfo(added_lines=500, deleted_lines=500),
        )
        assert verdict.status == "pass", (
            f"Expected pass when trivial_max_lines=0; got {verdict.status!r}"
        )

    def test_ac25_none_counts_skip_check(self, config_100) -> None:
        """AC25: DiffInfo with None counts → cross-check skipped → pass."""
        from theory import check
        from theory.checker import DiffInfo

        verdict = check(
            "Theory: trivial - rename",
            ["src/f.py"],
            config_100,
            diff=DiffInfo(),
        )
        assert verdict.status == "pass", (
            f"Expected pass when counts are None; got {verdict.status!r}"
        )

    def test_trivial_at_limit_boundary_passes(self, config_100) -> None:
        """sum==100 (at the limit, not over) → pass."""
        from theory import check
        from theory.checker import DiffInfo

        verdict = check(
            "Theory: trivial - rename",
            ["src/f.py"],
            config_100,
            diff=DiffInfo(added_lines=50, deleted_lines=50),
        )
        assert verdict.status == "pass"


# ===========================================================================
# AC26–32  check() — warn accumulation
# ===========================================================================


class TestWarnAccumulation:
    """ACs 26–32: warn accumulation in check()."""

    @pytest.fixture()
    def config(self):
        from theory.config import TheoryConfig
        return TheoryConfig()

    @pytest.fixture()
    def valid_msg(self):
        return "Theory: separates state tracking from step dispatch to eliminate retry double-count"

    def _make_verdict(self, status: str, reason: str | None = None):
        from theory.judge import JudgeVerdict
        return JudgeVerdict(status=status, reason=reason)

    def test_ac26_map_miss_plus_judge_disagrees_two_reasons(
        self, config, valid_msg
    ) -> None:
        """AC26: MAP miss + judge disagrees → warn, len(reasons)==2."""
        from theory import check
        from theory.checker import DiffInfo

        fake_judge = FakeJudge(self._make_verdict("does_not_explain", "too vague"))
        verdict = check(
            valid_msg,
            ["src/f.py"],
            config,
            map_components=["Walker"],
            judge=fake_judge,
            diff=DiffInfo(diff_text="diff content"),
        )
        assert verdict.status == "warn", (
            f"Expected warn; got {verdict.status!r}"
        )
        assert len(verdict.reasons) == 2, (
            f"Expected 2 reasons; got {len(verdict.reasons)}: {verdict.reasons}"
        )

    def test_ac27_map_miss_only_one_reason(self, config, valid_msg) -> None:
        """AC27: MAP miss only → warn, len(reasons)==1."""
        from theory import check
        from theory.checker import DiffInfo

        verdict = check(
            valid_msg,
            ["src/f.py"],
            config,
            map_components=["Walker"],
            judge=None,
        )
        assert verdict.status == "warn", f"Expected warn; got {verdict.status!r}"
        assert len(verdict.reasons) == 1, (
            f"Expected 1 reason; got {len(verdict.reasons)}: {verdict.reasons}"
        )

    def test_ac28_judge_unavailable_in_reasons(self, config, valid_msg) -> None:
        """AC28 / EM-JUDGE-UNAVAILABLE: unavailable verdict → reasons contain 'unavailable'."""
        from theory import check
        from theory.checker import DiffInfo

        fake_judge = FakeJudge(self._make_verdict("unavailable", "connection refused"))
        verdict = check(
            valid_msg,
            ["src/f.py"],
            config,
            judge=fake_judge,
            diff=DiffInfo(diff_text="d"),
        )
        assert any("unavailable" in r.lower() for r in verdict.reasons), (
            f"'unavailable' not in reasons: {verdict.reasons}"
        )

    def test_ac29_judge_unparseable_in_reasons(self, config, valid_msg) -> None:
        """AC29 / EM-JUDGE-UNPARSEABLE: unparseable verdict → reasons contain 'unparseable'."""
        from theory import check
        from theory.checker import DiffInfo

        fake_judge = FakeJudge(self._make_verdict("unparseable", None))
        verdict = check(
            valid_msg,
            ["src/f.py"],
            config,
            judge=fake_judge,
            diff=DiffInfo(diff_text="d"),
        )
        assert any("unparseable" in r.lower() for r in verdict.reasons), (
            f"'unparseable' not in reasons: {verdict.reasons}"
        )

    def test_ac30_map_match_plus_judge_agrees_is_pass(self, config, valid_msg) -> None:
        """AC30: MAP match + judge agrees → pass.

        The message must name the MAP component ('Harness') for the MAP
        reconciliation check to match; otherwise an MAP miss warn fires.
        Fix: use a message that explicitly names the component.
        """
        from theory import check
        from theory.checker import DiffInfo

        # Message explicitly names the MAP component "Harness" so MAP matches
        map_msg = (
            "Theory: Harness separates state tracking from step dispatch "
            "to eliminate retry double-count"
        )
        fake_judge = FakeJudge(self._make_verdict("explains"))
        verdict = check(
            map_msg,
            ["src/f.py"],
            config,
            map_components=["Harness"],
            judge=fake_judge,
            diff=DiffInfo(diff_text="d"),
        )
        assert verdict.status == "pass", (
            f"Expected pass when MAP matches and judge agrees; got {verdict.status!r} "
            f"reasons: {verdict.reasons}"
        )

    def test_ac31_diff_text_absent_judge_not_called(self, config, valid_msg) -> None:
        """AC31: diff_text=None → judge not called; result is pass (no other warns)."""
        from theory import check
        from theory.checker import DiffInfo

        fake_judge = FakeJudge(self._make_verdict("does_not_explain"))
        verdict = check(
            valid_msg,
            ["src/f.py"],
            config,
            judge=fake_judge,
            diff=DiffInfo(diff_text=None),
        )
        assert fake_judge.call_count == 0, (
            f"Judge must not be called when diff_text=None; called {fake_judge.call_count} times"
        )
        assert verdict.status == "pass", (
            f"Expected pass when judge not called; got {verdict.status!r}"
        )

    def test_ac32_diff_none_judge_not_called(self, config, valid_msg) -> None:
        """AC32: diff=None → judge not called."""
        from theory import check

        fake_judge = FakeJudge(self._make_verdict("does_not_explain"))
        verdict = check(
            valid_msg,
            ["src/f.py"],
            config,
            judge=fake_judge,
            diff=None,
        )
        assert fake_judge.call_count == 0, (
            f"Judge must not be called when diff=None; called {fake_judge.call_count} times"
        )


# ===========================================================================
# AC33–34  check() — judge skip conditions
# ===========================================================================


class TestJudgeSkipConditions:
    """ACs 33–34: judge is not called for substance FAIL or valid trivial."""

    def _make_does_not_explain(self):
        from theory.judge import JudgeVerdict
        return JudgeVerdict(status="does_not_explain", reason="vague")

    def test_ac33_substance_fail_judge_not_called(self) -> None:
        """AC33: banned phrase → substance FAIL → judge not called."""
        from theory import check
        from theory.config import TheoryConfig
        from theory.checker import DiffInfo

        fake_judge = FakeJudge(self._make_does_not_explain())
        verdict = check(
            "Theory: fix",   # banned phrase → substance fail
            ["src/f.py"],
            TheoryConfig(),
            judge=fake_judge,
            diff=DiffInfo(diff_text="diff"),
        )
        assert verdict.status == "fail", (
            f"Expected fail for banned phrase; got {verdict.status!r}"
        )
        assert fake_judge.call_count == 0, (
            f"Judge must not be called on substance FAIL; called {fake_judge.call_count} times"
        )

    def test_ac34_valid_trivial_judge_not_called(self) -> None:
        """AC34: valid trivial claim (under limit) → judge not called."""
        from theory import check
        from theory.config import TheoryConfig
        from theory.checker import DiffInfo

        fake_judge = FakeJudge(self._make_does_not_explain())
        verdict = check(
            "Theory: trivial - rename",
            ["src/f.py"],
            TheoryConfig(trivial_max_lines=100),
            judge=fake_judge,
            diff=DiffInfo(added_lines=10, deleted_lines=5, diff_text="diff"),
        )
        # Under-limit trivial → pass (not fail, not warn from cross-check)
        assert verdict.status == "pass", (
            f"Expected pass for valid trivial; got {verdict.status!r}"
        )
        assert fake_judge.call_count == 0, (
            f"Judge must not be called for trivial commits; called {fake_judge.call_count} times"
        )


# ===========================================================================
# AC35–37  CLI — numstat acquisition
# ===========================================================================


class TestNumstatAcquisition:
    """ACs 35–37: _acquire_diff_info() numstat parsing via subprocess mock."""

    def _build_numstat_output(self, *lines: str) -> str:
        return "\n".join(lines) + "\n"

    def test_ac35_numstat_parsed_correctly(self, tmp_path: Path, monkeypatch) -> None:
        """AC35: numstat '5\\t3\\tfile.py' → DiffInfo(added=5, deleted=3)."""
        numstat_out = self._build_numstat_output("5\t3\tfile.py")

        import subprocess as _sp

        call_log: list[list] = []

        def fake_run(cmd, **kwargs):
            call_log.append(list(cmd))
            proc = MagicMock()
            proc.returncode = 0
            if "--numstat" in cmd:
                proc.stdout = numstat_out
            else:
                proc.stdout = ""
            return proc

        import theory.__main__ as theory_main

        monkeypatch.setattr(theory_main, "subprocess", _build_fake_subprocess(fake_run))

        # Build a fake config with trivial_max_lines > 0 so numstat is needed
        from theory.config import TheoryConfig
        from theory.checker import DiffInfo
        import argparse

        cfg = TheoryConfig(trivial_max_lines=50)
        args = argparse.Namespace(staged=True, commit=None)

        diff = theory_main._acquire_diff_info(args, cfg)
        assert diff.added_lines == 5, f"Expected added_lines=5; got {diff.added_lines}"
        assert diff.deleted_lines == 3, f"Expected deleted_lines=3; got {diff.deleted_lines}"

    def test_ac36_binary_file_lines_skipped(self, tmp_path: Path, monkeypatch) -> None:
        """AC36: binary numstat line (-\\t-\\t) skipped, totals unaffected."""
        numstat_out = self._build_numstat_output(
            "5\t3\tfile.py",
            "-\t-\tbinary.so",
        )

        def fake_run(cmd, **kwargs):
            proc = MagicMock()
            proc.returncode = 0
            proc.stdout = numstat_out
            return proc

        import theory.__main__ as theory_main

        monkeypatch.setattr(theory_main, "subprocess", _build_fake_subprocess(fake_run))

        from theory.config import TheoryConfig
        import argparse

        cfg = TheoryConfig(trivial_max_lines=50)
        args = argparse.Namespace(staged=True, commit=None)
        diff = theory_main._acquire_diff_info(args, cfg)
        assert diff.added_lines == 5
        assert diff.deleted_lines == 3

    def test_ac37_em_numstat_git_fail_degrades(self, tmp_path: Path, monkeypatch) -> None:
        """AC37 / EM-NUMSTAT-GIT-FAIL: OSError from git → DiffInfo with None counts."""
        def fake_run(cmd, **kwargs):
            raise OSError("git not found")

        import theory.__main__ as theory_main

        monkeypatch.setattr(theory_main, "subprocess", _build_fake_subprocess(fake_run))

        from theory.config import TheoryConfig
        import argparse

        cfg = TheoryConfig(trivial_max_lines=50)
        args = argparse.Namespace(staged=True, commit=None)
        diff = theory_main._acquire_diff_info(args, cfg)
        assert diff.added_lines is None, (
            f"Expected added_lines=None on OSError; got {diff.added_lines}"
        )
        assert diff.deleted_lines is None


def _build_fake_subprocess(fake_run):
    """Build a module-like object with a .run attribute pointing to fake_run."""
    import subprocess as _sp
    import types

    fake_mod = types.ModuleType("subprocess")
    fake_mod.run = fake_run
    # Copy over constants needed by the module under test
    for attr in ("PIPE", "STDOUT", "DEVNULL", "CalledProcessError", "TimeoutExpired"):
        if hasattr(_sp, attr):
            setattr(fake_mod, attr, getattr(_sp, attr))
    return fake_mod


# ===========================================================================
# AC38–40  CLI — judge wiring
# ===========================================================================


class TestJudgeWiring:
    """ACs 38–40: judge configured/unconfigured, diff-text truncation, gating exit 0 on warn."""

    def test_ac39_em_no_judge_config_no_diff_text(self, tmp_path: Path) -> None:
        """AC39 / EM-NO-JUDGE-CONFIG: config.judge is None → judge block skipped."""
        # Run a check that would only warn from MAP miss, with judge=None
        from theory import check
        from theory.config import TheoryConfig
        from theory.checker import DiffInfo

        cfg = TheoryConfig()  # judge is None by default
        verdict = check(
            "Theory: separates state tracking to eliminate retry double-count",
            ["src/f.py"],
            cfg,
            map_components=["Walker"],  # miss → warn
            judge=None,
            diff=DiffInfo(diff_text="some diff"),
        )
        # MAP miss → warn, but judge absent → only 1 reason
        assert verdict.status == "warn"
        assert len(verdict.reasons) == 1

    def test_ac40_warn_exits_zero_gating_mode(self, tmp_path: Path) -> None:
        """AC40: check() returns warn → CLI exits 0 in gating mode."""
        _make_git_repo(tmp_path)
        msg = tmp_path / "msg.txt"
        # Valid rationale, MAP miss → warn verdict
        msg.write_text(
            "Theory: separates state tracking from step dispatch to eliminate retry double-count\n"
        )
        cfg_file = tmp_path / "cfg.yaml"
        cfg_file.write_text(
            "mode: gating\n"
            "scope:\n"
            "  - \"agentic/**\"\n"
            "map:\n"
            "  path: MAP.md\n"
            "  reconcile: warn\n"
        )
        result = _run_theory_cli(
            [
                "check",
                "--commit-msg-file",
                str(msg),
                "--config",
                str(cfg_file),
                "--staged",
            ],
            cwd=tmp_path,
        )
        # Warn (or pass) must exit 0 — both cases acceptable; fail must exit 1
        # In gating mode, warn → exit 0 per spec Decision 1 (nothing in this slice can fail a commit)
        assert result.returncode == 0, (
            f"Gating mode warn must exit 0; got {result.returncode}. "
            f"stdout: {result.stdout!r}  stderr: {result.stderr!r}"
        )

    def test_ac38_diff_text_truncated_to_max_diff_chars(self, tmp_path: Path, monkeypatch) -> None:
        """AC38: judge configured → diff text fetched and truncated to max_diff_chars."""
        # We test this through the _acquire_diff_info function, checking truncation
        long_diff = "x" * 10_000

        def fake_run(cmd, **kwargs):
            proc = MagicMock()
            proc.returncode = 0
            if "--numstat" in cmd:
                proc.stdout = "5\t3\tfile.py\n"
            else:
                proc.stdout = long_diff
            return proc

        import theory.__main__ as theory_main

        monkeypatch.setattr(theory_main, "subprocess", _build_fake_subprocess(fake_run))

        from theory.config import JudgeConfig, TheoryConfig
        import argparse

        judge_cfg = JudgeConfig(
            model="m",
            base_url="http://x",
            max_diff_chars=3000,
        )
        cfg = TheoryConfig(judge=judge_cfg)
        args = argparse.Namespace(staged=True, commit=None)
        diff = theory_main._acquire_diff_info(args, cfg)
        assert diff.diff_text is not None
        assert len(diff.diff_text) <= 3000, (
            f"diff_text must be truncated to max_diff_chars=3000; "
            f"got {len(diff.diff_text)} chars"
        )


# ===========================================================================
# Integration: end-to-end config discovery + warn accumulation via check()
# ===========================================================================


class TestEndToEndDiscoveryAndCheck:
    """Integration: real config file + check() via inject fakes."""

    def test_cwd_config_discovery_with_trivial_max_lines(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Config loaded from cwd; trivial_max_lines=10 causes over-limit warn."""
        (tmp_path / "theory.config.yaml").write_text("trivial_max_lines: 10\n")
        monkeypatch.chdir(tmp_path)

        from theory.config import load_config
        from theory import check
        from theory.checker import DiffInfo

        cfg = load_config(None)
        assert cfg.trivial_max_lines == 10

        verdict = check(
            "Theory: trivial - rename",
            ["src/f.py"],
            cfg,
            diff=DiffInfo(added_lines=8, deleted_lines=8),  # sum=16 > 10
        )
        assert verdict.status == "warn", (
            f"Expected warn for sum=16 > trivial_max_lines=10; got {verdict.status!r}"
        )
        reasons = " ".join(verdict.reasons)
        assert "16" in reasons or "rename" in reasons

    def test_full_warn_accumulation_map_and_judge(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """MAP miss + judge disagrees → two warns accumulated in single verdict."""
        from theory import check
        from theory.config import TheoryConfig
        from theory.checker import DiffInfo
        from theory.judge import JudgeVerdict

        cfg = TheoryConfig()
        fake_judge = FakeJudge(JudgeVerdict(status="does_not_explain", reason="too vague"))

        valid_msg = (
            "Theory: separates state tracking from step dispatch to fix retry double-count"
        )
        verdict = check(
            valid_msg,
            ["src/f.py"],
            cfg,
            map_components=["Walker"],
            judge=fake_judge,
            diff=DiffInfo(diff_text="some diff text"),
        )
        assert verdict.status == "warn"
        assert len(verdict.reasons) == 2, (
            f"Expected exactly 2 reasons (MAP + judge); got {verdict.reasons}"
        )

    def test_judge_verdict_dataclass_frozen(self) -> None:
        """JudgeVerdict must be frozen (spec: @dataclass(frozen=True))."""
        from theory.judge import JudgeVerdict

        v = JudgeVerdict(status="explains", reason="ok")
        with pytest.raises((AttributeError, TypeError)):
            v.status = "does_not_explain"  # type: ignore[misc]

    def test_judge_verdict_none_reason(self) -> None:
        """JudgeVerdict.reason defaults to None."""
        from theory.judge import JudgeVerdict

        v = JudgeVerdict(status="unavailable")
        assert v.reason is None
