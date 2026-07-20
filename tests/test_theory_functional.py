"""
Functional tests for Slice (u): ``theory_pass1_checker``

Written against the spec contract (origin-harness spec) only.
No reads of ``agentic/**`` or ``tests/test_*.py`` at authoring time.
No live Anthropic SDK calls — all tests are pure in-process calls or
subprocess invocations against ``python -m theory``.

Acceptance Criteria covered (all 18):
  AC1  – All six package files exist and are non-empty
  AC2  – Import succeeds without error in a clean process
  AC3  – parse_trailer basic extraction
  AC4  – parse_trailer absent → None
  AC5  – parse_trailer continuation line unfolded
  AC6  – check() banned+short phrase → fail
  AC7  – check() substantive rationale → pass
  AC8  – check() trivial rename → pass
  AC9  – check() unknown trivial class → fail with class name
  AC10 – check() out-of-scope with trailer → silent pass
  AC11 – check() out-of-scope no trailer → silent pass (EM8 not fired)
  AC12 – check() in-scope missing trailer → fail EM1
  AC13 – check() MAP component case-insensitive match → pass
  AC14 – check() MAP component miss → warn EM5
  AC15 – load_config(nonexistent) → defaults no exception
  AC16 – load_config() default: mode=advisory, min_length=20, rename in classes
  AC17 – CLI check exits 0 advisory / exits 1 gating; correct output prefixes
  AC18 – (full suite regression; verified by impl_validate)

Error modes covered (all 8):
  EM1  – missing Theory: trailer (AC12)
  EM2  – banned stock phrase (TestEvaluateSubstance + check tests)
  EM3  – trailer too short (TestEvaluateSubstance + check tests)
  EM4  – unknown trivial class (AC9)
  EM5  – MAP component miss (AC14)
  EM6  – install-hook conflict without --force
  EM7  – install-hook outside a git repo
  EM8  – out-of-scope commit → silent pass (AC10 / AC11)

Spec reference: origin-harness spec — slice u (theory_pass1_checker), 2026-06-11.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
# tests/functional/ -> tests/ -> project root
_ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_staged_repo(tmp_path: Path) -> None:
    """Initialise a temp git repo with src/foo.py staged."""
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.email", "qa@test.com"],
                   cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "QA"],
                   cwd=str(tmp_path), capture_output=True)
    agentic_dir = tmp_path / "agentic"
    agentic_dir.mkdir(exist_ok=True)
    (agentic_dir / "foo.py").write_text("x = 1\n")
    subprocess.run(["git", "add", str(agentic_dir / "foo.py")],
                   cwd=str(tmp_path), capture_output=True)


def _run_theory_cli(
    args: list[str],
    *,
    cwd: Path | None = None,
    env_extra: dict | None = None,
) -> subprocess.CompletedProcess:
    """Run ``python -m theory <args>`` ensuring the package is importable."""
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


# ===========================================================================
# AC1 — All six package files exist and are non-empty
# ===========================================================================

_EXPECTED_FILES = [
    "theory/__init__.py",
    "theory/__main__.py",
    "theory/checker.py",
    "theory/config.py",
    "theory/theory.config.yaml",
    "theory/hooks/commit-msg",
]


class TestPackageFilesExist:
    """AC1: All six deliverable files must exist and be non-empty."""

    @pytest.mark.parametrize("rel", _EXPECTED_FILES)
    def test_file_exists(self, rel: str) -> None:
        """AC1: file must exist at the spec-declared path."""
        assert (_ROOT / rel).exists(), (
            f"Expected file missing: {rel}. "
            "Spec AC1: all six deliverable files must be created."
        )

    @pytest.mark.parametrize("rel", _EXPECTED_FILES)
    def test_file_nonempty(self, rel: str) -> None:
        """AC1: file must be non-empty."""
        path = _ROOT / rel
        if path.exists():
            assert path.stat().st_size > 0, (
                f"File is empty: {rel}. "
                "Spec AC1: all deliverable files must be non-empty."
            )


# ===========================================================================
# AC2 — Import succeeds without error
# ===========================================================================


class TestImportContract:
    """AC2: All public symbols listed in __init__.__all__ must be importable."""

    def test_import_all_public_symbols(self) -> None:
        """AC2: top-level import of all eight public symbols succeeds."""
        from theory import (  # noqa: F401
            MapConfig,
            TheoryConfig,
            TheoryVerdict,
            check,
            evaluate_scope,
            evaluate_substance,
            load_config,
            parse_trailer,
        )

    def test_all_symbols_are_callable(self) -> None:
        """AC2: imported function symbols must be callable (not None)."""
        from theory import (
            check, evaluate_scope, evaluate_substance,
            load_config, parse_trailer,
        )
        for fn in [check, evaluate_scope, evaluate_substance, load_config, parse_trailer]:
            assert callable(fn), f"{fn!r} is not callable"

    def test_dunder_all_exports(self) -> None:
        """AC2: __all__ must contain all eight specified exports."""
        import theory as t
        expected = {
            "MapConfig", "TheoryConfig", "TheoryVerdict",
            "check", "evaluate_scope", "evaluate_substance",
            "load_config", "parse_trailer",
        }
        actual = set(t.__all__)
        missing = expected - actual
        assert not missing, (
            f"Missing from __all__: {sorted(missing)}. "
            "Spec AC2: __init__.py __all__ must export all eight symbols."
        )


# ===========================================================================
# AC3–5, negative paths — parse_trailer behaviour
# ===========================================================================


class TestParseTrailer:
    """AC3–5: parse_trailer extracts the Theory: trailer value per the spec rules."""

    def test_ac3_basic_extraction(self) -> None:
        """AC3: value after 'Theory: ' is returned stripped."""
        from theory import parse_trailer
        assert parse_trailer("Theory: why this matters\nOther: line") == "why this matters"

    def test_ac4_absent_returns_none(self) -> None:
        """AC4: no Theory: line → None returned."""
        from theory import parse_trailer
        assert parse_trailer("no Theory trailer here") is None

    def test_ac5_continuation_line_unfolded(self) -> None:
        """AC5: git-trailer continuation (single leading space) is unfolded with a space."""
        from theory import parse_trailer
        assert parse_trailer("Theory: first line\n  continuation here") == "first line continuation here"

    def test_header_case_sensitive(self) -> None:
        """Spec: 'Theory:' is case-sensitive; 'theory:' must NOT match."""
        from theory import parse_trailer
        assert parse_trailer("theory: lowercase header") is None

    def test_first_match_wins(self) -> None:
        """Spec: first Theory: line wins; subsequent Theory: lines are ignored."""
        from theory import parse_trailer
        result = parse_trailer("Theory: first\nTheory: second")
        assert result == "first"

    def test_indented_header_not_matched(self) -> None:
        """Spec: match only a line beginning at column 0; indented Theory: is ignored."""
        from theory import parse_trailer
        assert parse_trailer(" Theory: indented does not match") is None

    def test_empty_message_returns_none(self) -> None:
        """Empty commit message → None (no trailer present)."""
        from theory import parse_trailer
        assert parse_trailer("") is None


# ===========================================================================
# AC6–14 — check() pass / fail / warn paths
# ===========================================================================


class TestCheckPassPaths:
    """check() returns TheoryVerdict('pass', []) for all valid-pass inputs."""

    def test_ac7_substantive_rationale(self) -> None:
        """AC7: long, non-banned rationale → pass."""
        from theory import check, TheoryConfig
        result = check(
            "Theory: separates state tracking from step dispatch to fix the retry double-count",
            ["src/foo.py"],
            TheoryConfig(),
        )
        assert result.status == "pass"
        assert result.reasons == []

    def test_ac8_trivial_rename(self) -> None:
        """AC8: 'trivial - rename' is a valid trivial class → pass."""
        from theory import check, TheoryConfig
        result = check("Theory: trivial - rename", ["src/foo.py"], TheoryConfig())
        assert result.status == "pass"

    def test_all_default_trivial_classes_pass(self) -> None:
        """AC8 ext: all seven default trivial classes produce pass."""
        from theory import check, TheoryConfig
        for cls in ["rename", "formatting", "typo", "comment", "deps", "generated", "bookkeeping"]:
            result = check(f"Theory: trivial - {cls}", ["src/foo.py"], TheoryConfig())
            assert result.status == "pass", f"Expected pass for trivial - {cls}, got {result.status}"

    def test_ac10_out_of_scope_with_trailer(self) -> None:
        """AC10/EM8: out-of-scope file + trailer present → silent pass.

        Default scope is ["**"]; a narrowed config exercises out-of-scope.
        """
        from theory import check, TheoryConfig
        result = check(
            "Theory: why this matters",
            ["unrelated/path.txt"],
            TheoryConfig(scope=["src/**"]),
        )
        assert result.status == "pass"
        assert result.reasons == []

    def test_ac11_out_of_scope_no_trailer(self) -> None:
        """AC11/EM8: out-of-scope file + no trailer → silent pass (EM1 NOT fired)."""
        from theory import check, TheoryConfig
        result = check(
            "no trailer", ["unrelated/path.txt"], TheoryConfig(scope=["src/**"])
        )
        assert result.status == "pass"
        assert result.reasons == []

    def test_ac13_map_case_insensitive_match(self) -> None:
        """AC13: 'walker' in trailer matches 'Walker' in map_components → pass."""
        from theory import check, TheoryConfig
        result = check(
            "Theory: explains the design tradeoff in the walker state machine",
            ["src/foo.py"],
            TheoryConfig(),
            map_components=["Walker", "Harness"],
        )
        assert result.status == "pass"

    def test_em8_empty_changed_files_is_out_of_scope(self) -> None:
        """EM8: empty changed-files list → out-of-scope → silent pass."""
        from theory import check, TheoryConfig
        result = check("Theory: something interesting here", [], TheoryConfig())
        assert result.status == "pass"
        assert result.reasons == []


class TestCheckFailPaths:
    """check() returns TheoryVerdict('fail', ...) for all failure inputs."""

    def test_ac6_banned_phrase_returns_fail(self) -> None:
        """AC6: 'fixes' is a banned phrase AND too short → fail verdict."""
        from theory import check, TheoryConfig
        result = check("Theory: fixes", ["src/foo.py"], TheoryConfig())
        assert result.status == "fail"

    def test_ac6_fail_has_reasons(self) -> None:
        """AC6: fail verdict must carry at least one reason."""
        from theory import check, TheoryConfig
        result = check("Theory: fixes", ["src/foo.py"], TheoryConfig())
        assert len(result.reasons) >= 1

    def test_ac9_unknown_trivial_class(self) -> None:
        """AC9/EM4: 'unknownclass' not in trivial_classes → fail with class name in reason."""
        from theory import check, TheoryConfig
        result = check("Theory: trivial - unknownclass", ["src/foo.py"], TheoryConfig())
        assert result.status == "fail"
        assert any("unknownclass" in r for r in result.reasons)

    def test_ac12_em1_missing_trailer(self) -> None:
        """AC12/EM1: in-scope file, no Theory: trailer → fail with exact message."""
        from theory import check, TheoryConfig
        result = check("no trailer", ["src/foo.py"], TheoryConfig())
        assert result.status == "fail"
        assert result.reasons == ["missing Theory: trailer"]

    def test_em2_banned_stock_phrase_fix(self) -> None:
        """EM2: whole-value 'fix' is banned → fail with 'banned' in reason."""
        from theory import check, TheoryConfig
        result = check("Theory: fix", ["src/foo.py"], TheoryConfig())
        assert result.status == "fail"
        assert any("banned" in r.lower() or "fix" in r for r in result.reasons)

    def test_em2_banned_phrase_case_insensitive(self) -> None:
        """EM2: banned phrase matching is case-insensitive (FIX = fix)."""
        from theory import check, TheoryConfig
        result = check("Theory: FIX", ["src/foo.py"], TheoryConfig())
        assert result.status == "fail"

    def test_em3_trailer_too_short(self) -> None:
        """EM3: trailer shorter than min_length (20) and not banned → fail."""
        from theory import check, TheoryConfig
        # "short ok" is 8 chars, not in banned_phrases, but < 20
        result = check("Theory: short ok", ["src/foo.py"], TheoryConfig())
        assert result.status == "fail"
        assert any("short" in r.lower() for r in result.reasons)

    def test_em4_unknown_trivial_class_reason_contains_class_name(self) -> None:
        """EM4: unknown trivial class error message includes the class name."""
        from theory import check, TheoryConfig
        result = check("Theory: trivial - fancynewclass", ["src/foo.py"], TheoryConfig())
        assert result.status == "fail"
        assert any("fancynewclass" in r for r in result.reasons)


class TestCheckWarnPaths:
    """check() returns TheoryVerdict('warn', ...) for MAP-miss warnings."""

    def test_ac14_em5_map_component_miss(self) -> None:
        """AC14/EM5: valid rationale, no MAP component matched → warn."""
        from theory import check, TheoryConfig
        result = check(
            "Theory: explains the design tradeoff in the state machine",
            ["src/foo.py"],
            TheoryConfig(),
            map_components=["Walker", "Harness"],
        )
        assert result.status == "warn"

    def test_em5_warn_has_map_reason(self) -> None:
        """EM5: warn verdict must carry at least one reason about MAP / component."""
        from theory import check, TheoryConfig
        result = check(
            "Theory: explains the design tradeoff in the state machine",
            ["src/foo.py"],
            TheoryConfig(),
            map_components=["Walker", "Harness"],
        )
        assert len(result.reasons) >= 1
        assert any("map" in r.lower() or "component" in r.lower() for r in result.reasons)

    def test_no_map_components_skips_map_step(self) -> None:
        """When map_components is None, MAP reconciliation step is skipped → pass."""
        from theory import check, TheoryConfig
        result = check(
            "Theory: explains the design tradeoff in the state machine",
            ["src/foo.py"],
            TheoryConfig(),
            map_components=None,
        )
        assert result.status == "pass"


# ===========================================================================
# TheoryVerdict dataclass contract
# ===========================================================================


class TestTheoryVerdictDataclass:
    """TheoryVerdict is a dataclass with 'status' and 'reasons' fields."""

    def test_status_field_accessible(self) -> None:
        from theory import TheoryVerdict
        v = TheoryVerdict(status="pass")
        assert v.status == "pass"

    def test_reasons_field_accessible(self) -> None:
        from theory import TheoryVerdict
        v = TheoryVerdict(status="fail", reasons=["reason A"])
        assert v.reasons == ["reason A"]

    def test_reasons_defaults_to_empty_list(self) -> None:
        from theory import TheoryVerdict
        v = TheoryVerdict(status="pass")
        assert v.reasons == []

    def test_check_always_returns_theory_verdict_instance(self) -> None:
        """check() must always return a TheoryVerdict instance, never a dict or None."""
        from theory import check, TheoryConfig, TheoryVerdict
        for msg, files in [
            ("no trailer", ["src/foo.py"]),
            ("Theory: fix", ["src/foo.py"]),
            ("Theory: trivial - rename", ["src/foo.py"]),
            ("anything", []),
        ]:
            result = check(msg, files, TheoryConfig())
            assert isinstance(result, TheoryVerdict), (
                f"check() returned {type(result).__name__!r}, expected TheoryVerdict"
            )


# ===========================================================================
# MapConfig / TheoryConfig dataclass defaults
# ===========================================================================


class TestConfigDataclasses:
    """MapConfig and TheoryConfig defaults match the spec's theory.config.yaml."""

    def test_theory_config_default_mode(self) -> None:
        from theory import TheoryConfig
        assert TheoryConfig().mode == "advisory"

    def test_theory_config_default_min_length(self) -> None:
        from theory import TheoryConfig
        assert TheoryConfig().min_length == 20

    def test_theory_config_default_trivial_classes(self) -> None:
        from theory import TheoryConfig
        cfg = TheoryConfig()
        for cls in ["rename", "formatting", "typo", "comment", "deps", "generated", "bookkeeping"]:
            assert cls in cfg.trivial_classes, f"'{cls}' missing from default trivial_classes"

    def test_theory_config_default_banned_phrases(self) -> None:
        from theory import TheoryConfig
        cfg = TheoryConfig()
        for phrase in ["fix", "fixes", "needed", "cleanup", "update",
                       "wip", "misc", "changes", "improvements"]:
            assert phrase in cfg.banned_phrases, f"'{phrase}' missing from default banned_phrases"

    def test_map_config_default_path(self) -> None:
        from theory import MapConfig
        assert MapConfig().path == "MAP.md"

    def test_map_config_default_reconcile(self) -> None:
        from theory import MapConfig
        assert MapConfig().reconcile == "warn"

    def test_theory_config_default_scope_is_everything(self) -> None:
        from theory import TheoryConfig
        assert TheoryConfig().scope == ["**"], (
            f"Packaged default scope must be the generic ['**']; got {TheoryConfig().scope}"
        )


# ===========================================================================
# evaluate_scope — public API contract
# ===========================================================================


class TestEvaluateScope:
    """evaluate_scope(changed_files, scope_globs) → bool."""

    def test_in_scope_file_returns_true(self) -> None:
        from theory import evaluate_scope
        assert evaluate_scope(["src/foo.py"], ["src/**"]) is True

    def test_out_of_scope_returns_false(self) -> None:
        from theory import evaluate_scope
        assert evaluate_scope(["docs/readme.txt"], ["src/**", "tests/**"]) is False

    def test_empty_files_returns_false(self) -> None:
        from theory import evaluate_scope
        assert evaluate_scope([], ["src/**"]) is False

    def test_any_in_scope_file_is_sufficient(self) -> None:
        from theory import evaluate_scope
        assert evaluate_scope(
            ["docs/readme.txt", "src/core.py"],
            ["src/**"],
        ) is True

    def test_empty_scope_globs_returns_false(self) -> None:
        from theory import evaluate_scope
        assert evaluate_scope(["src/foo.py"], []) is False


# ===========================================================================
# evaluate_substance — public API contract
# ===========================================================================


class TestEvaluateSubstance:
    """evaluate_substance(trailer_value, config) → TheoryVerdict."""

    def test_pass_when_neither_rule_fires(self) -> None:
        from theory import evaluate_substance, TheoryConfig
        result = evaluate_substance(
            "separates state tracking from step dispatch",
            TheoryConfig(),
        )
        assert result.status == "pass"
        assert result.reasons == []

    def test_em3_fail_too_short(self) -> None:
        """EM3: value shorter than min_length → fail with 'short' in reason."""
        from theory import evaluate_substance, TheoryConfig
        result = evaluate_substance("too short", TheoryConfig())
        assert result.status == "fail"
        assert any("short" in r.lower() for r in result.reasons)

    def test_em2_fail_banned_phrase(self) -> None:
        """EM2: whole-value banned phrase → fail with 'banned' in reason."""
        from theory import evaluate_substance, TheoryConfig
        result = evaluate_substance("fix", TheoryConfig())
        assert result.status == "fail"
        assert any("banned" in r.lower() or "fix" in r.lower() for r in result.reasons)

    def test_both_rules_fire_independently(self) -> None:
        """EM2 + EM3: short AND banned → both reasons appear in verdict."""
        from theory import evaluate_substance, TheoryConfig
        # "fix" is 3 chars (< 20) AND banned
        result = evaluate_substance("fix", TheoryConfig())
        assert result.status == "fail"
        assert len(result.reasons) >= 2, (
            f"Expected >= 2 reasons (short + banned), got: {result.reasons}"
        )

    def test_em2_banned_phrase_case_insensitive(self) -> None:
        """EM2: banned phrase matching is case-insensitive."""
        from theory import evaluate_substance, TheoryConfig
        result = evaluate_substance("FIX", TheoryConfig())
        assert result.status == "fail"

    def test_em3_reason_references_threshold(self) -> None:
        """EM3: failure reason must reference the threshold (20) or word 'short'."""
        from theory import evaluate_substance, TheoryConfig
        # 5-char non-banned value: only EM3 fires
        result = evaluate_substance("hello", TheoryConfig())
        assert result.status == "fail"
        assert any("20" in r or "short" in r.lower() for r in result.reasons)


# ===========================================================================
# AC15–16 — load_config() contract
# ===========================================================================


class TestLoadConfig:
    """load_config() returns TheoryConfig from YAML or defaults on missing/null."""

    def test_ac15_nonexistent_path_returns_defaults(self, tmp_path: Path) -> None:
        """AC15: non-existent file → TheoryConfig() defaults, no exception raised."""
        from theory import load_config, TheoryConfig
        result = load_config(tmp_path / "does_not_exist.yaml")
        assert isinstance(result, TheoryConfig)
        assert result.mode == "advisory"
        assert result.min_length == 20

    def test_ac16_default_load_mode(self) -> None:
        """AC16: load_config() with no argument → mode is 'advisory'."""
        from theory import load_config
        assert load_config().mode == "advisory"

    def test_ac16_default_load_min_length(self) -> None:
        """AC16: load_config() with no argument → min_length is 20."""
        from theory import load_config
        assert load_config().min_length == 20

    def test_ac16_default_load_rename_in_trivial_classes(self) -> None:
        """AC16: load_config() with no argument → 'rename' in trivial_classes."""
        from theory import load_config
        assert "rename" in load_config().trivial_classes

    def test_empty_yaml_returns_defaults(self, tmp_path: Path) -> None:
        """Empty YAML file → TheoryConfig() defaults (not an error)."""
        empty = tmp_path / "empty.yaml"
        empty.write_text("")
        from theory import load_config, TheoryConfig
        result = load_config(empty)
        assert isinstance(result, TheoryConfig)
        assert result.mode == "advisory"

    def test_null_yaml_returns_defaults(self, tmp_path: Path) -> None:
        """YAML 'null' document → TheoryConfig() defaults."""
        null_f = tmp_path / "null.yaml"
        null_f.write_text("null\n")
        from theory import load_config, TheoryConfig
        result = load_config(null_f)
        assert isinstance(result, TheoryConfig)

    def test_non_mapping_yaml_raises_value_error(self, tmp_path: Path) -> None:
        """YAML root is a list (not a mapping) → raises ValueError containing 'mapping'."""
        bad = tmp_path / "bad.yaml"
        bad.write_text("- item1\n- item2\n")
        from theory import load_config
        with pytest.raises(ValueError, match="mapping"):
            load_config(bad)

    def test_partial_yaml_overrides_only_specified_keys(self, tmp_path: Path) -> None:
        """Partial YAML (only 'mode') → other keys retain defaults."""
        partial = tmp_path / "partial.yaml"
        partial.write_text("mode: gating\n")
        from theory import load_config
        result = load_config(partial)
        assert result.mode == "gating"
        assert result.min_length == 20  # default retained


# ===========================================================================
# AC17 — CLI check: advisory/gating exit codes and output format
# ===========================================================================


class TestCLICheckCommand:
    """AC17: CLI check command honours mode, exit codes, and output prefixes."""

    def test_advisory_mode_always_exits_zero(self, tmp_path: Path) -> None:
        """Advisory mode exits 0 regardless of verdict."""
        msg = tmp_path / "msg.txt"
        msg.write_text("no Theory trailer here\n")
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text("mode: advisory\nscope:\n  - \"agentic/**\"\n")
        result = _run_theory_cli(
            ["check", "--commit-msg-file", str(msg), "--config", str(cfg)],
            cwd=tmp_path,
        )
        assert result.returncode == 0, (
            f"Advisory mode must always exit 0; got {result.returncode}. "
            f"stderr: {result.stderr}"
        )

    def test_gating_mode_fail_exits_one(self, tmp_path: Path) -> None:
        """Gating mode + in-scope staged file + no Theory trailer → exit 1."""
        _setup_staged_repo(tmp_path)
        msg = tmp_path / "msg.txt"
        msg.write_text("no Theory trailer here\n")
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text("mode: gating\nscope:\n  - \"agentic/**\"\n")
        result = _run_theory_cli(
            ["check", "--commit-msg-file", str(msg),
             "--config", str(cfg), "--staged"],
            cwd=tmp_path,
        )
        assert result.returncode == 1, (
            f"Gating mode fail must exit 1; got {result.returncode}. "
            f"stdout: {result.stdout!r}  stderr: {result.stderr!r}"
        )

    def test_fail_advisory_outputs_advisory_prefix(self, tmp_path: Path) -> None:
        """Fail in advisory mode → each reason line prefixed with 'THEORY ADVISORY:'."""
        _setup_staged_repo(tmp_path)
        msg = tmp_path / "msg.txt"
        msg.write_text("no Theory trailer here\n")
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text("mode: advisory\nscope:\n  - \"agentic/**\"\n")
        result = _run_theory_cli(
            ["check", "--commit-msg-file", str(msg),
             "--config", str(cfg), "--staged"],
            cwd=tmp_path,
        )
        assert result.returncode == 0
        assert "THEORY ADVISORY:" in result.stdout, (
            f"Expected 'THEORY ADVISORY:' prefix in stdout; got: {result.stdout!r}"
        )

    def test_fail_gating_outputs_fail_prefix(self, tmp_path: Path) -> None:
        """Fail in gating mode → each reason line prefixed with 'THEORY FAIL:'."""
        _setup_staged_repo(tmp_path)
        msg = tmp_path / "msg.txt"
        msg.write_text("no Theory trailer here\n")
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text("mode: gating\nscope:\n  - \"agentic/**\"\n")
        result = _run_theory_cli(
            ["check", "--commit-msg-file", str(msg),
             "--config", str(cfg), "--staged"],
            cwd=tmp_path,
        )
        assert result.returncode == 1
        assert "THEORY FAIL:" in result.stdout, (
            f"Expected 'THEORY FAIL:' prefix in stdout; got: {result.stdout!r}"
        )

    def test_pass_produces_no_stdout(self, tmp_path: Path) -> None:
        """Pass verdict → no stdout output (silent pass)."""
        _setup_staged_repo(tmp_path)
        msg = tmp_path / "msg.txt"
        msg.write_text(
            "Theory: separates state tracking from step dispatch to eliminate retry double-count\n"
        )
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text("mode: advisory\nscope:\n  - \"agentic/**\"\n")
        result = _run_theory_cli(
            ["check", "--commit-msg-file", str(msg),
             "--config", str(cfg), "--staged"],
            cwd=tmp_path,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "", (
            f"Pass verdict must produce no stdout; got: {result.stdout!r}"
        )

    def test_out_of_scope_commit_no_output_gating(self, tmp_path: Path) -> None:
        """EM8 CLI: out-of-scope staged file → no stdout, exit 0 even in gating mode."""
        _setup_staged_repo(tmp_path)
        msg = tmp_path / "msg.txt"
        msg.write_text("no Theory trailer\n")
        # Scope deliberately excludes agentic/** → staged src/foo.py is out-of-scope
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text("mode: gating\nscope:\n  - \"docs/**\"\n")
        result = _run_theory_cli(
            ["check", "--commit-msg-file", str(msg),
             "--config", str(cfg), "--staged"],
            cwd=tmp_path,
        )
        assert result.returncode == 0, (
            f"Out-of-scope commit must exit 0 even in gating mode; got {result.returncode}"
        )
        assert result.stdout.strip() == "", (
            f"Out-of-scope commit must produce no output; got: {result.stdout!r}"
        )

    def test_no_import_errors_from_cli(self, tmp_path: Path) -> None:
        """CLI startup must not crash with ImportError or ModuleNotFoundError."""
        msg = tmp_path / "msg.txt"
        msg.write_text("no trailer\n")
        result = _run_theory_cli(
            ["check", "--commit-msg-file", str(msg)],
            cwd=tmp_path,
        )
        assert "ModuleNotFoundError" not in result.stderr
        assert "ImportError" not in result.stderr


# ===========================================================================
# EM6 / EM7 — install-hook error modes (CLI)
# ===========================================================================


class TestInstallHookErrors:
    """EM6 / EM7: install-hook error modes per the spec."""

    def test_em7_not_a_git_repo_exits_one(self, tmp_path: Path) -> None:
        """EM7: no .git directory present → exit 1 with error message on stderr."""
        fake_git = tmp_path / ".git"  # does NOT exist
        result = _run_theory_cli(
            ["install-hook", "--git-dir", str(fake_git)],
        )
        assert result.returncode == 1, (
            f"Expected exit 1 when .git does not exist; got {result.returncode}"
        )
        assert result.stderr.strip() != "", (
            "install-hook must write an error to stderr when .git dir is absent."
        )

    def test_em6_existing_non_sample_hook_exits_one(self, tmp_path: Path) -> None:
        """EM6: existing non-sample hook + no --force → exit 1, file unchanged.

        NOTE: The spec detects 'sample' (case-insensitive) in the first 5 lines.
        This hook deliberately avoids that word entirely.
        """
        git_dir = tmp_path / ".git"
        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        hook_file = hooks_dir / "commit-msg"
        # Content must NOT contain 'sample' (spec: /sample/i in first 5 lines = safe to overwrite)
        original = "#!/bin/sh\n# custom hook for commit verification\necho 'running hook'\n"
        hook_file.write_text(original)

        result = _run_theory_cli(
            ["install-hook", "--git-dir", str(git_dir)],
        )
        assert result.returncode == 1, (
            f"Expected exit 1 for conflicting hook without --force; got {result.returncode}"
        )
        assert hook_file.read_text() == original, "Hook file must be unchanged on conflict."

    def test_em6_force_flag_overwrites_hook(self, tmp_path: Path) -> None:
        """EM6: --force allows overwriting a non-sample hook → exit 0."""
        git_dir = tmp_path / ".git"
        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        hook_file = hooks_dir / "commit-msg"
        hook_file.write_text("#!/bin/sh\n# custom hook for commit verification\n")

        result = _run_theory_cli(
            ["install-hook", "--git-dir", str(git_dir), "--force"],
        )
        assert result.returncode == 0, (
            f"--force must succeed; got {result.returncode}  stderr: {result.stderr}"
        )
        new_content = hook_file.read_text()
        assert "theory" in new_content, (
            "Hook file must contain the theory shim after --force install."
        )

    def test_install_success_on_clean_hooks_dir(self, tmp_path: Path) -> None:
        """Successful install: no pre-existing hook → exit 0, shim written."""
        git_dir = tmp_path / ".git"
        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir(parents=True)

        result = _run_theory_cli(
            ["install-hook", "--git-dir", str(git_dir)],
        )
        assert result.returncode == 0, (
            f"Clean install must succeed; stderr: {result.stderr}"
        )
        hook_file = hooks_dir / "commit-msg"
        assert hook_file.exists(), "commit-msg hook file must be created."
        assert "theory" in hook_file.read_text()

    def test_sample_hook_is_overwritable_without_force(self, tmp_path: Path) -> None:
        """Sample hook (contains 'sample' in first 5 lines) → overwritable without --force."""
        git_dir = tmp_path / ".git"
        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        hook_file = hooks_dir / "commit-msg"
        # Contains 'sample' → spec says this is safe to overwrite
        hook_file.write_text("#!/bin/sh\n# This is a sample hook\necho sample\n")

        result = _run_theory_cli(
            ["install-hook", "--git-dir", str(git_dir)],
        )
        assert result.returncode == 0, (
            f"Sample hook must be overwritable without --force; stderr: {result.stderr}"
        )
