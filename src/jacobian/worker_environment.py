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

_DEFAULT_LOCALE = "C.UTF-8"


def worker_environment(
    *,
    extra_variables: tuple[str, ...] = (),
    overrides: dict[str, str] | None = None,
    path_prefix: str | None = None,
    locale: str = _DEFAULT_LOCALE,
) -> dict[str, str]:
    """Return only variables needed to start a deterministic Python worker.

    *extra_variables* are passed through from the host environment when
    present. *overrides* take precedence over both host pass-through and the
    deterministic defaults. *path_prefix* is prepended to ``PATH`` when
    provided. *locale* sets ``LANG`` and ``LC_ALL`` (default ``C.UTF-8``).
    """

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
            "LANG": locale,
            "LC_ALL": locale,
        }
    )
    if path_prefix:
        existing = environment.get("PATH", "")
        environment["PATH"] = (
            f"{path_prefix}{os.pathsep}{existing}" if existing else path_prefix
        )
    if overrides:
        environment.update(overrides)
    return environment
