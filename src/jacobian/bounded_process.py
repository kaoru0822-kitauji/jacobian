"""Bounded subprocess capture for local plugin and checker isolation.

Children run in their own process group. Reader threads cap retained output and
terminate the whole group as soon as either stream exceeds its limit. Timeouts
also terminate descendants rather than only the immediate worker.
"""

from __future__ import annotations

import os
import signal
import subprocess
import tempfile
import threading
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from typing import BinaryIO


@dataclass(frozen=True, slots=True)
class BoundedProcessResult:
    returncode: int | None
    stdout: bytes
    stderr: bytes
    stdout_exceeded: bool
    stderr_exceeded: bool
    timed_out: bool


def _kill_process_tree(process: subprocess.Popen[bytes]) -> None:
    """Best-effort termination of a worker and every descendant it created."""

    if os.name == "posix":
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        return

    if os.name == "nt":  # pragma: no cover - exercised in cross-platform CI
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
        )
        return

    process.kill()  # pragma: no cover - defensive fallback


def _capture_stream(
    stream: BinaryIO,
    *,
    limit: int,
    process: subprocess.Popen[bytes],
    captured: bytearray,
    exceeded: threading.Event,
) -> None:
    total = 0
    read_chunk = getattr(stream, "read1", stream.read)
    try:
        while chunk := read_chunk(64 * 1024):
            total += len(chunk)
            remaining = max(0, limit - len(captured))
            captured.extend(chunk[:remaining])
            if total > limit:
                exceeded.set()
                _kill_process_tree(process)
                return
    except (OSError, ValueError):
        # The coordinator may close the pipe after killing descendants that
        # retained it beyond the operation deadline.
        return


def run_bounded_process(
    command: Sequence[str],
    *,
    input_bytes: bytes,
    timeout_seconds: float,
    environment: Mapping[str, str],
    stdout_limit: int,
    stderr_limit: int,
) -> BoundedProcessResult:
    """Run a child while bounding output, elapsed time, and process lifetime."""

    if stdout_limit < 0 or stderr_limit < 0:
        raise ValueError("subprocess output limits must be nonnegative")
    if timeout_seconds <= 0:
        raise ValueError("subprocess timeout must be positive")

    start_new_session = os.name == "posix"
    creationflags = (
        int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        if os.name == "nt"
        else 0
    )

    stdout = bytearray()
    stderr = bytearray()
    stdout_exceeded = threading.Event()
    stderr_exceeded = threading.Event()
    timed_out = False

    with tempfile.TemporaryFile() as stdin_file:
        stdin_file.write(input_bytes)
        stdin_file.seek(0)
        process = subprocess.Popen(
            command,
            stdin=stdin_file,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            start_new_session=start_new_session,
            creationflags=creationflags,
        )
        assert process.stdout is not None
        assert process.stderr is not None

        readers = (
            threading.Thread(
                target=_capture_stream,
                kwargs={
                    "stream": process.stdout,
                    "limit": stdout_limit,
                    "process": process,
                    "captured": stdout,
                    "exceeded": stdout_exceeded,
                },
                daemon=True,
            ),
            threading.Thread(
                target=_capture_stream,
                kwargs={
                    "stream": process.stderr,
                    "limit": stderr_limit,
                    "process": process,
                    "captured": stderr,
                    "exceeded": stderr_exceeded,
                },
                daemon=True,
            ),
        )
        for reader in readers:
            reader.start()

        deadline = time.monotonic() + timeout_seconds
        try:
            process.wait(timeout=max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_process_tree(process)
            process.wait()
        finally:
            for reader in readers:
                reader.join(timeout=max(0.0, deadline - time.monotonic()))
            if any(reader.is_alive() for reader in readers):
                # The immediate worker may have exited after spawning a
                # descendant that inherited stdout or stderr.  In that case
                # process.wait() succeeds while the pipes never reach EOF.
                timed_out = True
                _kill_process_tree(process)
            process.stdout.close()
            process.stderr.close()
            for reader in readers:
                reader.join(timeout=0.1)

    return BoundedProcessResult(
        returncode=process.returncode,
        stdout=bytes(stdout),
        stderr=bytes(stderr),
        stdout_exceeded=stdout_exceeded.is_set(),
        stderr_exceeded=stderr_exceeded.is_set(),
        timed_out=timed_out,
    )
