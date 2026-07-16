"""PostToolUse hook: validate prompt artifacts written by Write/Edit.

Author-side teeth for PromptLang (SPEC §5 artifact classes): when the
edited file matches a file rule that imposes tag requirements, run the
validator and feed failures back to the agent (exit 2, stderr). Every
other branch — non-matching path, docs-class rule, a machine without
prompt_lang installed, malformed hook input — exits 0 silently: the
hook must never break a session on a machine that hasn't adopted the
standard.

A repo-local ``prompt-lang.config.yaml`` at the session cwd overrides
the packaged default config.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("tool_name") not in ("Write", "Edit"):
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    if not isinstance(file_path, str) or not file_path.endswith(".md"):
        return 0
    path = Path(file_path)
    if not path.is_file():
        return 0

    try:
        from prompt_lang.config import load_config
        from prompt_lang.validator import match_file_rule, validate_file
    except Exception:
        return 0  # standard not installed on this machine — degrade silently

    try:
        repo_config = Path("prompt-lang.config.yaml")
        config = load_config(repo_config if repo_config.is_file() else None)
        rule = match_file_rule(path, config)
        if rule is None or not (rule.required_tags or rule.forbidden_tags):
            return 0  # not a claimed prompt artifact (docs/reference classes skip)
        result = validate_file(path, config)
    except Exception:
        return 0  # enforcement must never crash the session

    if result.passed:
        return 0

    print(f"PromptLang: {path} fails validation:", file=sys.stderr)
    for err in result.errors[:10]:
        print(f"  line {err.line}: {err.message}", file=sys.stderr)
    print(
        "Fix the file to conform (spec: standards/promptlang/SPEC.md in foundations).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
