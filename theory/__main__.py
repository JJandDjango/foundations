"""Enables `python -m theory check ...` and `python -m theory install-hook`."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


def main(argv: "list[str] | None" = None) -> int:
    """CLI entry point.  Returns integer exit code.

    Commands
    --------
    check
        --commit-msg-file <path>   Path to commit message file (required)
        --staged                   Derive changed files via git diff --cached --name-only
        --commit <sha>             Derive changed files via git show --name-only --format= <sha>
        --config <path>            Config file override (default: cwd theory.config.yaml, else packaged default)
        --mode <advisory|gating>   Mode override (default: from config)

        Output (stdout):
          status="pass"            no output
          status="warn"            one line per reason: "THEORY ADVISORY: <reason>"
          status="fail", advisory  one line per reason: "THEORY ADVISORY: <reason>"
          status="fail", gating    one line per reason: "THEORY FAIL: <reason>"
          out-of-scope commit      no output

        Exit codes:
          advisory mode            always 0
          gating mode              0 (pass or warn), 1 (fail)

    install-hook
        --git-dir <path>           Target git directory (default: .git relative to cwd)
        --force                    Overwrite an existing non-sample hook

        Copies theory/hooks/commit-msg into <git-dir>/hooks/commit-msg.
        Exits 0 on success; exits 1 and prints an error to stderr when the target
        file already exists and is non-sample content and --force is not given.
        A non-existent .git directory (not a git repo) exits 1 with an error.
    """
    parser = argparse.ArgumentParser(
        prog="python -m theory",
        description="Theory commit-boundary checker",
    )
    subparsers = parser.add_subparsers(dest="command")

    # check sub-command
    check_parser = subparsers.add_parser("check", help="Check a commit message")
    check_parser.add_argument(
        "--commit-msg-file", required=True, help="Path to commit message file"
    )
    staged_group = check_parser.add_mutually_exclusive_group()
    staged_group.add_argument(
        "--staged",
        action="store_true",
        help="Derive changed files from staged index",
    )
    staged_group.add_argument(
        "--commit", metavar="SHA", help="Derive changed files from a commit SHA"
    )
    check_parser.add_argument("--config", metavar="PATH", help="Config file override")
    check_parser.add_argument(
        "--mode",
        choices=["advisory", "gating"],
        help="Mode override (default: from config)",
    )

    # install-hook sub-command
    install_parser = subparsers.add_parser(
        "install-hook", help="Install git commit-msg hook"
    )
    install_parser.add_argument(
        "--git-dir",
        default=".git",
        metavar="PATH",
        help="Target git directory (default: .git)",
    )
    install_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing non-sample hook",
    )

    args = parser.parse_args(argv)

    if args.command == "check":
        return _cmd_check(args)
    elif args.command == "install-hook":
        return _cmd_install_hook(args)
    else:
        parser.print_help()
        return 0


def _acquire_diff_info(
    args: argparse.Namespace,
    config: "TheoryConfig",  # type: ignore[name-defined]
) -> "DiffInfo":  # type: ignore[name-defined]
    """Acquire numstat (line counts) and optionally diff text from git."""
    from theory.checker import DiffInfo

    need_numstat = config.trivial_max_lines > 0 or config.judge is not None
    need_diff_text = config.judge is not None

    added: "int | None" = None
    deleted: "int | None" = None
    diff_text: "str | None" = None

    has_source = getattr(args, "staged", False) or getattr(args, "commit", None)

    # Decode all git output as UTF-8 with replacement: git content is UTF-8, but
    # subprocess text mode defaults to the OS locale codec (cp1252 on Windows,
    # strict), which crashes on bytes undefined there (e.g. 0x90).
    if need_numstat and has_source:
        if args.staged:
            numstat_cmd = ["git", "diff", "--cached", "--numstat"]
        else:
            numstat_cmd = ["git", "show", "--numstat", "--format=", args.commit]
        try:
            result = subprocess.run(
                numstat_cmd, capture_output=True,
                encoding="utf-8", errors="replace", check=False
            )
            if result.returncode == 0:
                a_total, d_total = 0, 0
                for line in result.stdout.splitlines():
                    parts = line.split("\t", 2)
                    if len(parts) < 2:
                        continue
                    if parts[0] == "-" or parts[1] == "-":
                        continue  # binary file entry
                    try:
                        a_total += int(parts[0])
                        d_total += int(parts[1])
                    except ValueError:
                        continue
                added, deleted = a_total, d_total
        except OSError:
            pass  # degrade to None fields

    if need_diff_text and has_source:
        if args.staged:
            diff_cmd = ["git", "diff", "--cached"]
        else:
            diff_cmd = ["git", "show", "--format=", args.commit]
        try:
            result = subprocess.run(
                diff_cmd, capture_output=True,
                encoding="utf-8", errors="replace", check=False
            )
            if result.returncode == 0:
                max_chars = config.judge.max_diff_chars  # type: ignore[union-attr]
                diff_text = result.stdout[:max_chars]
        except OSError:
            pass

    return DiffInfo(added_lines=added, deleted_lines=deleted, diff_text=diff_text)


def _cmd_check(args: argparse.Namespace) -> int:
    """Execute the 'check' sub-command."""
    from theory.checker import check, load_map_components
    from theory.config import load_config

    config = load_config(args.config)
    if args.mode:
        config.mode = args.mode

    # Read commit message
    commit_msg_path = Path(args.commit_msg_file)
    try:
        commit_msg = commit_msg_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: could not read commit message file: {exc}", file=sys.stderr)
        return 1

    # Derive changed files
    changed_files: list[str] = []
    if args.staged:
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            changed_files = [f for f in result.stdout.splitlines() if f.strip()]
        except OSError:
            pass
    elif args.commit:
        try:
            result = subprocess.run(
                ["git", "show", "--name-only", "--format=", args.commit],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            changed_files = [f for f in result.stdout.splitlines() if f.strip()]
        except OSError:
            pass

    # Acquire diff info (numstat + diff text) when needed
    diff = _acquire_diff_info(args, config)

    # Construct judge if configured
    judge = None
    if config.judge is not None:
        from theory.judge import TheoryJudge
        judge = TheoryJudge.from_config(config.judge)

    # Load MAP components (silent failure if absent or unreadable)
    map_components = load_map_components(config.map.path)

    # Run check
    verdict = check(commit_msg, changed_files, config, map_components, diff=diff, judge=judge)

    # Emit output
    if verdict.status == "pass":
        return 0
    elif verdict.status == "warn":
        for reason in verdict.reasons:
            print(f"THEORY ADVISORY: {reason}")
        return 0
    else:  # fail
        if config.mode == "gating":
            for reason in verdict.reasons:
                print(f"THEORY FAIL: {reason}")
            return 1
        else:
            for reason in verdict.reasons:
                print(f"THEORY ADVISORY: {reason}")
            return 0


def _cmd_install_hook(args: argparse.Namespace) -> int:
    """Execute the 'install-hook' sub-command."""
    git_dir = Path(args.git_dir)

    if not git_dir.exists():
        print(
            f"error: git directory not found: {git_dir}",
            file=sys.stderr,
        )
        return 1

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    hook_dest = hooks_dir / "commit-msg"

    # Refuse non-sample overwrite unless --force given
    if hook_dest.exists() and not args.force:
        try:
            content = hook_dest.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            content = ""
        first_lines = "\n".join(content.splitlines()[:5])
        if not re.search(r"sample", first_lines, re.IGNORECASE):
            print(
                f"error: {hook_dest} already exists with non-sample content. "
                "Use --force to overwrite.",
                file=sys.stderr,
            )
            return 1

    # Copy the hook shim
    hook_src = Path(__file__).parent / "hooks" / "commit-msg"
    try:
        shutil.copy2(str(hook_src), str(hook_dest))
        # Ensure the hook is executable
        current_mode = hook_dest.stat().st_mode
        hook_dest.chmod(current_mode | 0o111)
        return 0
    except OSError as exc:
        print(f"error: could not install hook: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
