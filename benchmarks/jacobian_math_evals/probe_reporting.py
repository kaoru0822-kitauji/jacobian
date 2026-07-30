"""Stable, machine-independent reporting for source probe failures."""

from __future__ import annotations

from pathlib import Path


def probe_error_message(error: BaseException, *, cache_dir: Path) -> str:
    """Return an error message without embedding the local cache location."""

    message = str(error)
    cache_root = str(cache_dir.resolve())
    return message.replace(cache_root, "<cache-dir>")
