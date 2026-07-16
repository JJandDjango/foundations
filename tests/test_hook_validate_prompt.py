"""Three-branch contract of the author-side hook (hooks/validate_prompt.py).

The hook must be silent for everything that is not a claimed, failing
prompt artifact — that silence is what makes it safe on machines that
never adopted the standard.
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "validate_prompt.py"

VALID_PROMPT = textwrap.dedent(
    """\
    ---
    name: dev
    description: Developer agent
    ---

    <purpose>Implement features.</purpose>
    <instructions>
    1. Read the spec.
    </instructions>
    """
)


def _run_hook(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )


def _payload(path: Path, tool: str = "Write") -> dict:
    return {"tool_name": tool, "tool_input": {"file_path": str(path)}}


def test_non_matching_path_is_silent(tmp_path: Path) -> None:
    f = tmp_path / "notes.md"
    f.write_text("just prose\n", encoding="utf-8")
    proc = _run_hook(_payload(f))
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr == ""


def test_matching_valid_artifact_passes(tmp_path: Path) -> None:
    agent_dir = tmp_path / ".agentic" / "agents"
    agent_dir.mkdir(parents=True)
    f = agent_dir / "dev.md"
    f.write_text(VALID_PROMPT, encoding="utf-8")
    proc = _run_hook(_payload(f))
    assert proc.returncode == 0, proc.stderr


def test_matching_malformed_artifact_feeds_back(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "broken"
    skill_dir.mkdir(parents=True)
    f = skill_dir / "SKILL.md"
    f.write_text("no frontmatter, no tags\n", encoding="utf-8")
    proc = _run_hook(_payload(f))
    assert proc.returncode == 2
    assert "fails validation" in proc.stderr


def test_malformed_hook_input_is_silent() -> None:
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json at all",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert proc.returncode == 0
    assert proc.stderr == ""
