"""POSIX-style glob matcher with proper ``**`` semantics (SPEC §5).

Vendored into ``prompt_lang`` — deliberately dependency-free.
Python's stdlib ``fnmatch`` treats ``*`` as "match any including ``/``" —
which is the wrong behavior for path-segmented globs. This module provides
a regex-backed compiler that honors the gitignore-style semantics:

- ``**`` matches any number of path components (including zero) when used
  as a full segment; any characters (including ``/``) when embedded.
- ``*``  matches any run of non-``/`` characters.
- ``?``  matches exactly one non-``/`` character.

Character classes (``[abc]``) are not supported in v0.1.
"""

from __future__ import annotations

import os
import re


_CASE_FLAG = re.IGNORECASE if os.name == "nt" else 0


def compile_glob(pattern: str) -> re.Pattern[str]:
    """Compile a POSIX-style glob pattern to an anchored regex.

    The result is case-insensitive on Windows to match filesystem
    semantics; case-sensitive on Unix.
    """
    out: list[str] = []
    i = 0
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                i += 2
                if i < n and pattern[i] == "/":
                    i += 1
                    out.append("(?:[^/]+/)*")
                else:
                    out.append(".*")
            else:
                out.append("[^/]*")
                i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("^" + "".join(out) + "$", _CASE_FLAG)


def glob_match(pattern: str, path: str) -> bool:
    """Return True if ``path`` matches ``pattern`` per the above semantics."""
    return bool(compile_glob(pattern).match(path))
