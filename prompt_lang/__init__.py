"""Prompt Programming Language (PromptLang) — validates prompt files.

The canonical spec is ``standards/promptlang/SPEC.md`` in this repository;
this package is its forcing function. Validates one file at a time:
frontmatter, tag structure, reference-gating, semantic rules, token
budget, directives grammar. Cross-file integrity (do referenced files
exist, do names resolve) is a consumer's lint layer's job, not this
package's.

CLI: ``python -m prompt_lang <path> [--config <yaml>]``.
"""

from prompt_lang.config import (
    Config,
    DirectiveConfig,
    FileRule,
    FrontmatterConfig,
    InstructionConfig,
    TokenConfig,
    ValidationConfig,
    load_config,
)
from prompt_lang.errors import ValidationError, ValidationResult

__all__ = [
    "Config",
    "DirectiveConfig",
    "FileRule",
    "FrontmatterConfig",
    "InstructionConfig",
    "TokenConfig",
    "ValidationConfig",
    "ValidationError",
    "ValidationResult",
    "load_config",
]
