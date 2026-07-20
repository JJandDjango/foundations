"""Theory commit-boundary checker — teeth for the theory member standard.

Enforces that every in-scope git commit carries a Theory: trailer:
either a substantive rationale (≥ min_length chars, not a banned phrase) or
an explicit trivial-class escape.  Ships advisory; tightens to gating by
config.  The core is deterministic (no LLM); the optional substance judge
is config-gated and warn-only.  Spec: standards/theory/SPEC.md.
"""

from theory.checker import (
    TheoryVerdict,
    check,
    evaluate_scope,
    evaluate_substance,
    parse_trailer,
)
from theory.config import MapConfig, TheoryConfig, load_config

__all__ = [
    "MapConfig",
    "TheoryConfig",
    "TheoryVerdict",
    "check",
    "evaluate_scope",
    "evaluate_substance",
    "load_config",
    "parse_trailer",
]
