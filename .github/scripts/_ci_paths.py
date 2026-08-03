"""Shared path-decoding policy for the CI planner scripts.

These helpers are the single source of truth for turning a ``PATHS`` input
(JSON array, newline list, or shell-quoted tokens) into repository-relative
paths.  Every planner (``classify-ci-paths``, ``plan-local-tests``, and
``plan-benchmarks``) imports them so that normalization policy cannot drift
between the control planes.
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path

__all__ = ["normalize_paths", "path_values"]


def path_values(raw: str) -> list[str]:
    """Decode a PATHS input without making callers manufacture a Git diff."""

    raw = raw.strip()
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = None
    if isinstance(value, list):
        if not all(isinstance(path, str) for path in value):
            raise ValueError("PATHS JSON must be an array of strings")
        return list(value)
    if value is not None:
        raise ValueError("PATHS JSON must be an array of strings")
    return raw.splitlines() if "\n" in raw else shlex.split(raw)


def normalize_paths(paths: list[str]) -> list[str]:
    """Reject non-repository-relative paths and strip leading ``./``."""

    normalized: list[str] = []
    for path in paths:
        path = path.replace("\\", "/")
        if not path or path.startswith("/") or ".." in Path(path).parts:
            raise ValueError(f"changed path must be repository-relative: {path!r}")
        normalized.append(path.removeprefix("./"))
    return normalized
