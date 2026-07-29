"""Killable child-process control for process and provider boundary tests."""

from __future__ import annotations

import os
import signal
import subprocess
from collections.abc import Sequence
from pathlib import Path


def run_killable(
    argv: Sequence[str],
    *,
    cwd: str | Path | None = None,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    """Run a command with a parent-owned deadline and process-group cleanup."""

    process = subprocess.Popen(
        list(argv),
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=(os.name != "nt"),
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":  # pragma: no cover - Windows boundary lane
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        raise TimeoutError(
            f"command exceeded {timeout:.1f}s deadline: {list(argv)!r}; "
            f"stderr={stderr[-500:]!r}"
        ) from None
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
