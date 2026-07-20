"""Configuration for the Theory commit-boundary checker.

Mirrors the prompt_lang config loading style:
- Missing file → defaults
- Empty YAML → defaults
- Non-mapping YAML → ValueError
- Partial keys → dataclass defaults for missing keys

Discovery is three-tier: explicit path > cwd ``theory.config.yaml`` >
packaged default.  The cwd tier exists because the commit-msg hook invokes
the CLI with no arguments — a repo customizes by dropping the file at its
root, never by editing the packaged default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).parent / "theory.config.yaml"


@dataclass
class MapConfig:
    """MAP.md reconciliation settings."""

    path: str = "MAP.md"
    reconcile: str = "warn"  # only "warn" is valid in v1


@dataclass
class JudgeConfig:
    """LLM judge configuration block."""

    model: str
    base_url: str
    timeout_s: float = 10.0
    max_diff_chars: int = 6000


@dataclass
class TheoryConfig:
    """Complete theory-checker configuration."""

    mode: str = "advisory"  # "advisory" | "gating"
    scope: list[str] = field(
        default_factory=lambda: [
            "**",  # everything in scope by default; repos narrow via config
        ]
    )
    trivial_classes: list[str] = field(
        default_factory=lambda: [
            "rename",
            "formatting",
            "typo",
            "comment",
            "deps",
            "generated",
            "bookkeeping",
        ]
    )
    banned_phrases: list[str] = field(
        default_factory=lambda: [
            "fix",
            "fixes",
            "needed",
            "cleanup",
            "update",
            "wip",
            "misc",
            "changes",
            "improvements",
        ]
    )
    min_length: int = 20
    map: MapConfig = field(default_factory=MapConfig)
    trivial_max_lines: int = 100   # 0 disables the cross-check
    judge: "JudgeConfig | None" = None


def load_config(config_path: "Path | str | None" = None) -> TheoryConfig:
    """Load TheoryConfig from YAML.  Missing file → defaults."""
    if config_path is None:
        # Three-tier discovery: explicit > cwd-local > package default
        cwd_config = Path("theory.config.yaml")
        if cwd_config.exists():
            config_path = cwd_config
        else:
            config_path = _DEFAULT_CONFIG_PATH
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        return TheoryConfig()

    with config_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not data:
        return TheoryConfig()
    if not isinstance(data, dict):
        raise ValueError(
            f"theory config at {config_path} must be a YAML mapping"
        )
    return _parse_config(data)


def _parse_config(data: dict[str, Any]) -> TheoryConfig:
    """Build a TheoryConfig from a parsed YAML mapping, filling in defaults."""
    defaults = TheoryConfig()

    map_raw = data.get("map") or {}
    default_map = MapConfig()
    map_cfg = MapConfig(
        path=str(map_raw.get("path", default_map.path)),
        reconcile=str(map_raw.get("reconcile", default_map.reconcile)),
    )

    # trivial_max_lines
    trivial_max_lines = int(data.get("trivial_max_lines", defaults.trivial_max_lines))

    # judge block
    judge_raw = data.get("judge")
    judge: "JudgeConfig | None" = None
    if judge_raw is not None:
        if not isinstance(judge_raw, dict):
            raise ValueError("theory config: 'judge' must be a YAML mapping")
        model = judge_raw.get("model")
        base_url = judge_raw.get("base_url")
        if not isinstance(model, str) or not model:
            raise ValueError(
                "theory config: 'judge.model' is required and must be a non-empty string"
            )
        if not isinstance(base_url, str) or not base_url:
            raise ValueError(
                "theory config: 'judge.base_url' is required and must be a non-empty string"
            )
        judge = JudgeConfig(
            model=model,
            base_url=base_url,
            timeout_s=float(judge_raw.get("timeout_s", 10.0)),
            max_diff_chars=int(judge_raw.get("max_diff_chars", 6000)),
        )

    return TheoryConfig(
        mode=str(data.get("mode", defaults.mode)),
        scope=list(data.get("scope", defaults.scope)),
        trivial_classes=list(data.get("trivial_classes", defaults.trivial_classes)),
        banned_phrases=list(data.get("banned_phrases", defaults.banned_phrases)),
        min_length=int(data.get("min_length", defaults.min_length)),
        map=map_cfg,
        trivial_max_lines=trivial_max_lines,
        judge=judge,
    )
