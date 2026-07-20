"""Tests for the :mod:`theory` CLI (`python -m theory`).

Covers:
- advisory mode exits 0 on FAIL verdict
- gating mode exits 1 on FAIL and 0 on warn
- out-of-scope commit exits 0 in both modes (no output)
- install-hook into an empty temp git repo creates the hook file (AC1 path existence)
- install-hook refuses non-sample hook without --force (EM6)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_theory(
    *args: str,
    cwd: "str | Path | None" = None,
) -> subprocess.CompletedProcess:
    """Run `python -m theory <args>` and return CompletedProcess."""
    cmd = [sys.executable, "-m", "theory"] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


def _make_git_repo(tmp_path: Path, name: str = "repo") -> Path:
    """Create a minimal git repo at tmp_path/name; return the repo root."""
    repo_dir = tmp_path / name
    repo_dir.mkdir()
    subprocess.run(
        ["git", "init", str(repo_dir)],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        capture_output=True,
        check=True,
        cwd=str(repo_dir),
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        capture_output=True,
        check=True,
        cwd=str(repo_dir),
    )
    return repo_dir


def _stage_in_scope_file(repo_dir: Path) -> None:
    """Create and stage an in-scope file so --staged returns it."""
    src_dir = repo_dir / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "placeholder.py").write_text("# placeholder\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "src/placeholder.py"],
        capture_output=True,
        check=True,
        cwd=str(repo_dir),
    )


# ---------------------------------------------------------------------------
# Advisory mode
# ---------------------------------------------------------------------------


class TestCheckAdvisoryMode:
    """Advisory mode always exits 0."""

    pytestmark = pytest.mark.slow  # calls _run_theory (subprocess) + _make_git_repo (git)

    def test_advisory_in_scope_fail_exits_0(self, tmp_path: Path) -> None:
        """advisory: missing trailer on in-scope file → print advisory, exit 0."""
        repo_dir = _make_git_repo(tmp_path)
        _stage_in_scope_file(repo_dir)

        msg_file = repo_dir / "commit-msg.txt"
        msg_file.write_text("no theory trailer\n", encoding="utf-8")

        result = _run_theory(
            "check",
            "--commit-msg-file",
            str(msg_file),
            "--staged",
            cwd=repo_dir,
        )
        assert result.returncode == 0

    def test_advisory_in_scope_fail_prints_advisory_prefix(self, tmp_path: Path) -> None:
        """advisory: fail verdict → 'THEORY ADVISORY:' lines printed."""
        repo_dir = _make_git_repo(tmp_path)
        _stage_in_scope_file(repo_dir)

        msg_file = repo_dir / "commit-msg.txt"
        msg_file.write_text("no theory trailer\n", encoding="utf-8")

        result = _run_theory(
            "check",
            "--commit-msg-file",
            str(msg_file),
            "--staged",
            cwd=repo_dir,
        )
        assert "THEORY ADVISORY" in result.stdout

    def test_advisory_out_of_scope_exits_0_no_output(self, tmp_path: Path) -> None:
        """advisory: out-of-scope commit (empty changed_files) → exit 0, no output."""
        msg_file = tmp_path / "commit-msg.txt"
        msg_file.write_text("no theory trailer\n", encoding="utf-8")

        # No --staged or --commit → empty changed_files → out-of-scope
        result = _run_theory("check", "--commit-msg-file", str(msg_file))
        assert result.returncode == 0
        assert result.stdout == ""


# ---------------------------------------------------------------------------
# Gating mode
# ---------------------------------------------------------------------------


class TestCheckGatingMode:
    """Gating mode exits 1 on FAIL, 0 on warn or pass."""

    pytestmark = pytest.mark.slow  # calls _run_theory (subprocess) + _make_git_repo (git)

    def test_gating_in_scope_fail_exits_1(self, tmp_path: Path) -> None:
        """gating: missing trailer on in-scope file → exit 1."""
        repo_dir = _make_git_repo(tmp_path)
        _stage_in_scope_file(repo_dir)

        msg_file = repo_dir / "commit-msg.txt"
        msg_file.write_text("no theory trailer\n", encoding="utf-8")

        result = _run_theory(
            "check",
            "--commit-msg-file",
            str(msg_file),
            "--staged",
            "--mode",
            "gating",
            cwd=repo_dir,
        )
        assert result.returncode == 1

    def test_gating_in_scope_fail_prints_theory_fail_prefix(self, tmp_path: Path) -> None:
        """gating: fail verdict → 'THEORY FAIL:' lines printed."""
        repo_dir = _make_git_repo(tmp_path)
        _stage_in_scope_file(repo_dir)

        msg_file = repo_dir / "commit-msg.txt"
        msg_file.write_text("no theory trailer\n", encoding="utf-8")

        result = _run_theory(
            "check",
            "--commit-msg-file",
            str(msg_file),
            "--staged",
            "--mode",
            "gating",
            cwd=repo_dir,
        )
        assert "THEORY FAIL" in result.stdout

    def test_gating_out_of_scope_exits_0(self, tmp_path: Path) -> None:
        """gating: out-of-scope commit → exit 0."""
        msg_file = tmp_path / "commit-msg.txt"
        msg_file.write_text("no theory trailer\n", encoding="utf-8")

        result = _run_theory(
            "check", "--commit-msg-file", str(msg_file), "--mode", "gating"
        )
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# install-hook
# ---------------------------------------------------------------------------


class TestInstallHook:
    """install-hook creates hook file and respects non-sample protection."""

    pytestmark = pytest.mark.slow  # calls _make_git_repo (git subprocess) + _run_theory

    def test_install_into_empty_repo_creates_hook(self, tmp_path: Path) -> None:
        """AC1: install-hook copies theory/hooks/commit-msg into .git/hooks/."""
        repo_dir = _make_git_repo(tmp_path)
        git_dir = repo_dir / ".git"

        result = _run_theory("install-hook", "--git-dir", str(git_dir))
        assert result.returncode == 0
        hook_file = git_dir / "hooks" / "commit-msg"
        assert hook_file.exists()

    def test_installed_hook_contains_theory_invocation(self, tmp_path: Path) -> None:
        """Installed hook contains 'theory' invocation."""
        repo_dir = _make_git_repo(tmp_path)
        git_dir = repo_dir / ".git"

        _run_theory("install-hook", "--git-dir", str(git_dir))
        hook_file = git_dir / "hooks" / "commit-msg"
        content = hook_file.read_text(encoding="utf-8")
        assert "theory" in content

    def test_install_refuses_non_sample_without_force(self, tmp_path: Path) -> None:
        """EM6: existing non-sample hook → exit 1, file unchanged without --force."""
        repo_dir = _make_git_repo(tmp_path)
        git_dir = repo_dir / ".git"
        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir(exist_ok=True)

        original_content = "#!/bin/sh\necho 'custom existing hook'\n"
        hook_file = hooks_dir / "commit-msg"
        hook_file.write_text(original_content, encoding="utf-8")

        result = _run_theory("install-hook", "--git-dir", str(git_dir))
        assert result.returncode == 1
        # File should be unchanged
        assert hook_file.read_text(encoding="utf-8") == original_content

    def test_install_force_overwrites_non_sample(self, tmp_path: Path) -> None:
        """--force allows overwriting a non-sample hook."""
        repo_dir = _make_git_repo(tmp_path)
        git_dir = repo_dir / ".git"
        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir(exist_ok=True)

        hook_file = hooks_dir / "commit-msg"
        hook_file.write_text("#!/bin/sh\necho 'existing hook'\n", encoding="utf-8")

        result = _run_theory("install-hook", "--git-dir", str(git_dir), "--force")
        assert result.returncode == 0
        content = hook_file.read_text(encoding="utf-8")
        assert "theory" in content

    def test_install_non_git_dir_exits_1(self, tmp_path: Path) -> None:
        """EM7: non-existent .git directory → exit 1."""
        result = _run_theory(
            "install-hook", "--git-dir", str(tmp_path / "nonexistent" / ".git")
        )
        assert result.returncode == 1

    def test_install_overwrites_sample_hook_without_force(self, tmp_path: Path) -> None:
        """A hook containing 'sample' in first 5 lines can be replaced without --force."""
        repo_dir = _make_git_repo(tmp_path)
        git_dir = repo_dir / ".git"
        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir(exist_ok=True)

        hook_file = hooks_dir / "commit-msg"
        hook_file.write_text(
            "#!/bin/sh\n# An example sample hook\necho done\n", encoding="utf-8"
        )

        result = _run_theory("install-hook", "--git-dir", str(git_dir))
        assert result.returncode == 0
        content = hook_file.read_text(encoding="utf-8")
        assert "theory" in content


# ---------------------------------------------------------------------------
# T10: TestNumstatAcquisition — numstat parsing (ACs 35-37)
# ---------------------------------------------------------------------------


class TestNumstatAcquisition:
    """_acquire_diff_info() numstat parsing (ACs 35-37)."""

    def test_ac35_staged_numstat_produces_diff_info(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC35: numstat '5\t3\tfile.py' -> DiffInfo(added_lines=5, deleted_lines=3)."""
        import argparse
        import subprocess as subprocess_mod
        from theory.__main__ import _acquire_diff_info
        from theory.checker import DiffInfo
        from theory.config import TheoryConfig

        fake_result = subprocess_mod.CompletedProcess(
            args=[], returncode=0, stdout="5\t3\tfile.py\n", stderr=""
        )

        def fake_run(cmd, **kwargs):
            return fake_result

        monkeypatch.setattr("theory.__main__.subprocess.run", fake_run)

        args = argparse.Namespace(staged=True, commit=None)
        config = TheoryConfig()  # trivial_max_lines=100
        diff = _acquire_diff_info(args, config)
        assert diff.added_lines == 5
        assert diff.deleted_lines == 3

    def test_ac36_binary_file_line_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC36: '-\t-\tbinary.so' line is skipped, does not contribute to totals."""
        import argparse
        import subprocess as subprocess_mod
        from theory.__main__ import _acquire_diff_info
        from theory.config import TheoryConfig

        fake_result = subprocess_mod.CompletedProcess(
            args=[], returncode=0,
            stdout="-\t-\tbinary.so\n5\t3\tfile.py\n",
            stderr="",
        )

        def fake_run(cmd, **kwargs):
            return fake_result

        monkeypatch.setattr("theory.__main__.subprocess.run", fake_run)

        args = argparse.Namespace(staged=True, commit=None)
        config = TheoryConfig()
        diff = _acquire_diff_info(args, config)
        assert diff.added_lines == 5
        assert diff.deleted_lines == 3

    def test_ac37_git_oserror_degrades_gracefully(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC37: git numstat OSError -> DiffInfo with None counts -> no crash."""
        import argparse
        from theory.__main__ import _acquire_diff_info
        from theory.config import TheoryConfig

        def fake_run(cmd, **kwargs):
            raise OSError("git not found")

        monkeypatch.setattr("theory.__main__.subprocess.run", fake_run)

        args = argparse.Namespace(staged=True, commit=None)
        config = TheoryConfig()
        diff = _acquire_diff_info(args, config)
        # Should not raise; counts are None
        assert diff.added_lines is None
        assert diff.deleted_lines is None


# ---------------------------------------------------------------------------
# T10: TestJudgeWiring — diff text acquisition and warn exit code (ACs 38-40)
# ---------------------------------------------------------------------------


class TestJudgeWiring:
    """_acquire_diff_info() diff-text truncation and gating warn exits 0 (ACs 38-40)."""

    def test_ac38_diff_text_truncated_to_max_diff_chars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC38: diff text truncated to config.judge.max_diff_chars characters."""
        import argparse
        import subprocess as subprocess_mod
        from theory.__main__ import _acquire_diff_info
        from theory.config import JudgeConfig, TheoryConfig

        long_diff = "x" * 10000
        call_log: list = []

        def fake_run(cmd, **kwargs):
            call_log.append(cmd)
            return subprocess_mod.CompletedProcess(
                args=[], returncode=0, stdout=long_diff, stderr=""
            )

        monkeypatch.setattr("theory.__main__.subprocess.run", fake_run)

        judge_cfg = JudgeConfig(model="m", base_url="http://x", max_diff_chars=500)
        config = TheoryConfig(judge=judge_cfg)
        args = argparse.Namespace(staged=True, commit=None)
        diff = _acquire_diff_info(args, config)

        assert diff.diff_text is not None
        assert len(diff.diff_text) == 500

    def test_ac39_no_judge_config_no_diff_text(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AC39: config.judge is None -> no diff text fetched (diff_text is None)."""
        import argparse
        from theory.__main__ import _acquire_diff_info
        from theory.config import TheoryConfig

        # trivial_max_lines=0 means no numstat either, so subprocess never called
        config = TheoryConfig(trivial_max_lines=0)  # judge is None by default
        args = argparse.Namespace(staged=True, commit=None)

        calls: list = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            raise AssertionError(f"subprocess called unexpectedly with {cmd}")

        monkeypatch.setattr("theory.__main__.subprocess.run", fake_run)

        diff = _acquire_diff_info(args, config)
        assert diff.diff_text is None
        assert len(calls) == 0  # subprocess never called

    @pytest.mark.slow  # uses _make_git_repo (git subprocess) + _run_theory
    def test_ac40_warn_exits_zero_gating_mode(self, tmp_path: Path) -> None:
        """AC40: check() returning warn in gating mode -> exit 0."""
        # Create a commit message with a valid Theory trailer
        msg_file = tmp_path / "commit-msg.txt"
        msg_file.write_text(
            "Theory: extends the walker to support parallel stage execution\n",
            encoding="utf-8",
        )

        # Run with no --staged/--commit (empty changed_files → out-of-scope → pass)
        # That's too easy. Instead, create a git repo with in-scope changes and
        # pass an MAP file that causes a warn.
        repo_dir = _make_git_repo(tmp_path)
        _stage_in_scope_file(repo_dir)

        # Create an MAP.md with a component not mentioned in the commit msg
        map_path = repo_dir / "MAP.md"
        map_path.write_text(
            "---\ncomponents:\n  - name: NonExistentComponent\n---\n",
            encoding="utf-8",
        )

        # Write a config that enables MAP reconciliation with a component
        # not in the trailer → warn
        config_path = repo_dir / "theory.test.yaml"
        config_path.write_text(
            "mode: gating\n"
            "map:\n  path: MAP.md\n  reconcile: warn\n",
            encoding="utf-8",
        )

        result = _run_theory(
            "check",
            "--commit-msg-file", str(msg_file),
            "--staged",
            "--config", str(config_path),
            "--mode", "gating",
            cwd=repo_dir,
        )
        # Warn → exit 0 in gating mode
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# #133 live-fire regression: git diff decoded as UTF-8, not the locale codec
# ---------------------------------------------------------------------------


class TestDiffTextEncoding:
    """Regression: git output is decoded UTF-8, never the OS locale codec.

    On Windows, subprocess text mode defaults to cp1252 (strict), which raises
    UnicodeDecodeError on bytes undefined there -- e.g. 0x90, a UTF-8
    continuation byte present in many multibyte sequences. A real commit diff
    bearing such bytes crashed _acquire_diff_info (stdout -> None -> TypeError)
    before the judge ran. Found by the #133 judge live-fire on commit 1648ece.
    The fakes in TestNumstatAcquisition/TestJudgeWiring return pre-decoded str,
    so only a real git subprocess over non-cp1252 content exercises this path.
    """

    pytestmark = pytest.mark.slow  # _make_git_repo + real subprocess.run (git commit)

    def test_commit_diff_with_non_cp1252_bytes_does_not_crash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """git show diff with 0x90 bytes -> decoded, no crash, text populated."""
        import argparse
        from theory.__main__ import _acquire_diff_info
        from theory.config import JudgeConfig, TheoryConfig

        repo_dir = _make_git_repo(tmp_path)
        src_dir = repo_dir / "src"
        src_dir.mkdir(exist_ok=True)
        # U+2010 HYPHEN = E2 80 90 and Cyrillic А U+0410 = D0 90 both embed 0x90,
        # undefined in cp1252 and fatal to a strict locale decode.
        (src_dir / "unicode_file.py").write_text(
            "# theory test ‐ Ад — done\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "add", "src/unicode_file.py"],
            capture_output=True, check=True, cwd=str(repo_dir),
        )
        subprocess.run(
            ["git", "commit", "-m", "add unicode file"],
            capture_output=True, check=True, cwd=str(repo_dir),
        )
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, cwd=str(repo_dir),
        ).stdout.strip()

        monkeypatch.chdir(repo_dir)
        config = TheoryConfig(
            judge=JudgeConfig(model="m", base_url="http://localhost:1/v1")
        )
        args = argparse.Namespace(staged=False, commit=sha)

        # Must not raise UnicodeDecodeError / TypeError.
        diff = _acquire_diff_info(args, config)

        assert diff.diff_text is not None
        assert "unicode_file.py" in diff.diff_text
        assert diff.added_lines is not None and diff.added_lines >= 1
