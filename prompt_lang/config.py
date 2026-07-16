"""Configuration for prompt-lang validation (SPEC §5).

``FileRule.allow_reference`` gates the ``reference: true`` opt-out
(SPEC §1.3). All optional ``FileRule`` fields — ``skip_frontmatter``,
``skip_required_tags``, ``allow_reference`` — survive the YAML
round-trip (regression-tested).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


_DEFAULT_CONFIG_PATH = Path(__file__).parent / "prompt-lang.config.yaml"


@dataclass
class TokenConfig:
    """Token-count thresholds for warn/fail."""

    warn_at: int = 2000
    fail_at: int = 4000


@dataclass
class FrontmatterConfig:
    """YAML frontmatter field requirements."""

    required: list[str] = field(default_factory=lambda: ["name", "description"])
    optional: list[str] = field(
        default_factory=lambda: ["model", "argument-hint", "tools", "agent", "color"]
    )


@dataclass
class DirectiveConfig:
    """Directive-syntax configuration for routing rules (DELEGATE/CHAIN/etc.)."""

    keywords: list[str] = field(
        default_factory=lambda: ["DELEGATE", "DEFAULT", "CHAIN", "REQUIRE"]
    )
    patterns: dict[str, str] = field(
        default_factory=lambda: {
            "DELEGATE": r"^DELEGATE @[\w-]+ WHEN [\w, -]+$",
            "DEFAULT": r"^DEFAULT @[\w-]+$",
            # §10.6: CHAIN accepts ASCII "->" in addition to the Unicode arrow.
            "CHAIN": r"^CHAIN [\w-]+: @[\w-]+(\s*(?:->|→)\s*@[\w-]+)+$",
            # §10.6: REQUIRE permits quoted paths that contain spaces.
            "REQUIRE": r'^REQUIRE (?:"[^"]+"|\S+) ON \w+$',
        }
    )


@dataclass
class InstructionConfig:
    """Instruction-step action-keyword enforcement.

    Default is ``False`` in v0.1: only strict orchestrator-style prompts
    typically want numbered steps to begin with a capital-letter action
    keyword. The shipped default YAML matches.
    """

    enforce_actions: bool = False
    action_keywords: list[str] = field(
        default_factory=lambda: [
            "ROUTE",
            "LOAD",
            "DELEGATE",
            "VERIFY",
            "EXECUTE",
            "SYNTHESIZE",
            "REPORT",
            "PARSE",
            "CHECK",
        ]
    )


@dataclass
class FileRule:
    """File-specific tag requirements keyed off fnmatch patterns.

    ``allow_reference`` (SPEC §1.3): when True, files matching this rule
    may opt out of full validation by setting ``reference: true`` in
    their frontmatter. Default-deny.
    """

    pattern: str
    required_tags: list[str] = field(default_factory=list)
    forbidden_tags: list[str] = field(default_factory=list)
    skip_frontmatter: bool = False
    skip_required_tags: bool = False
    allow_reference: bool = False


@dataclass
class ValidationConfig:
    """Complete validation configuration."""

    tokens: TokenConfig = field(default_factory=TokenConfig)
    semantic_check: bool = True
    required_tags: list[str] = field(
        default_factory=lambda: ["purpose", "instructions"]
    )
    optional_tags: list[str] = field(
        default_factory=lambda: [
            "variables",
            "context",
            "constraints",
            "examples",
            "output",
            "criteria",
            "routing",
            "directives",
        ]
    )
    ambiguous_patterns: list[str] = field(
        default_factory=lambda: [
            "maybe",
            "might",
            "consider",
            "optionally",
            "try to",
            "possibly",
            "it would be good to",
            "you could",
            "perhaps",
        ]
    )
    frontmatter: FrontmatterConfig = field(default_factory=FrontmatterConfig)
    directives: DirectiveConfig = field(default_factory=DirectiveConfig)
    instructions: InstructionConfig = field(default_factory=InstructionConfig)

    @property
    def all_tags(self) -> list[str]:
        """Union of required + optional tag names."""
        return self.required_tags + self.optional_tags


@dataclass
class Config:
    """Root configuration object."""

    validation: ValidationConfig = field(default_factory=ValidationConfig)
    file_rules: list[FileRule] = field(default_factory=list)


def load_config(config_path: Path | str | None = None) -> Config:
    """Load configuration from YAML. Missing file → defaults."""
    if config_path is None:
        config_path = _DEFAULT_CONFIG_PATH
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        return Config()

    with config_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if not data:
        return Config()
    if not isinstance(data, dict):
        raise ValueError(
            f"prompt-lang config at {config_path} must be a YAML mapping"
        )
    return _parse_config(data)


def _parse_config(data: dict[str, Any]) -> Config:
    v = data.get("validation", {}) or {}

    tokens_data = v.get("tokens") or {}
    tokens = TokenConfig(
        warn_at=int(tokens_data.get("warn_at", 2000)),
        fail_at=int(tokens_data.get("fail_at", 4000)),
    )

    fm_data = v.get("frontmatter") or {}
    frontmatter = FrontmatterConfig(
        required=list(
            fm_data.get("required", FrontmatterConfig().required)
        ),
        optional=list(
            fm_data.get("optional", FrontmatterConfig().optional)
        ),
    )

    dir_data = data.get("directives") or {}
    default_directives = DirectiveConfig()
    directives = DirectiveConfig(
        keywords=list(dir_data.get("keywords", default_directives.keywords)),
        patterns=dict(dir_data.get("patterns", default_directives.patterns)),
    )

    inst_data = data.get("instructions") or {}
    default_instructions = InstructionConfig()
    instructions = InstructionConfig(
        enforce_actions=bool(
            inst_data.get("enforce_actions", default_instructions.enforce_actions)
        ),
        action_keywords=list(
            inst_data.get("action_keywords", default_instructions.action_keywords)
        ),
    )

    validation = ValidationConfig(
        tokens=tokens,
        semantic_check=bool(v.get("semantic_check", True)),
        required_tags=list(v.get("required_tags", ValidationConfig().required_tags)),
        optional_tags=list(v.get("optional_tags", ValidationConfig().optional_tags)),
        ambiguous_patterns=list(
            v.get("ambiguous_patterns", ValidationConfig().ambiguous_patterns)
        ),
        frontmatter=frontmatter,
        directives=directives,
        instructions=instructions,
    )

    # Every optional FileRule field passes through; a field dropped here
    # is a regression (covered by tests).
    raw_rules = data.get("file_rules") or []
    file_rules: list[FileRule] = []
    for rule in raw_rules:
        if not isinstance(rule, dict):
            raise ValueError(f"file_rules entry must be a mapping, got {rule!r}")
        file_rules.append(
            FileRule(
                pattern=str(rule.get("pattern", "")),
                required_tags=list(rule.get("required_tags", [])),
                forbidden_tags=list(rule.get("forbidden_tags", [])),
                skip_frontmatter=bool(rule.get("skip_frontmatter", False)),
                skip_required_tags=bool(rule.get("skip_required_tags", False)),
                allow_reference=bool(rule.get("allow_reference", False)),
            )
        )

    return Config(validation=validation, file_rules=file_rules)
