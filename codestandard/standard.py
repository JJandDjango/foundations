"""Load the house code standard (layer 1) from the packaged data file.

The default is the read-only packaged ``codestandard/code_standard.yaml`` —
the single source of the house numbers.  A consumer overrides via
``--standard <path>`` (or the ``path`` argument here), never by mutating the
packaged file; ``hard_max`` entries keep "hard-gated" honest under overrides.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _default_standard_path() -> Path:
    """Resolve the packaged house standard beside this module."""
    return Path(__file__).parent / "code_standard.yaml"


def load_standard(path: Path | None = None) -> dict:
    """Load the house code standard from disk.

    Args:
        path: Explicit path override. When ``None``, resolves to the packaged
              ``codestandard/code_standard.yaml``.

    Returns:
        Parsed dict with at minimum the keys ``version`` (str) and ``rules``
        (dict mapping rule-name -> rule-config-dict).

    Raises:
        FileNotFoundError: if the resolved path does not exist.
        ValueError: if the YAML is missing ``version`` or ``rules``.
    """
    resolved = _default_standard_path() if path is None else Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"code standard not found: {resolved}")
    with resolved.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if "version" not in data or "rules" not in data:
        raise ValueError(
            f"code standard {resolved} missing required keys 'version' and/or 'rules'"
        )
    return data
