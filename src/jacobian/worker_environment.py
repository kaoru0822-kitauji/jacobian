"""Minimal environment shared by local worker subprocesses."""

from __future__ import annotations

import os

_PORTABLE_VARIABLES = (
    "PATH",
    "PYTHONPATH",
    "HOME",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TMPDIR",
)
_WINDOWS_VARIABLES = (
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "TEMP",
    "TMP",
)


def worker_environment(
    *,
    extra_variables: tuple[str, ...] = (),
) -> dict[str, str]:
    """Return only variables needed to start a deterministic Python worker."""

    selected: tuple[str, ...] = _PORTABLE_VARIABLES + extra_variables
    if os.name == "nt":
        selected += _WINDOWS_VARIABLES
    environment = {
        name: value for name in selected if (value := os.environ.get(name)) is not None
    }
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "TZ": "UTC",
        }
    )
    return environment
