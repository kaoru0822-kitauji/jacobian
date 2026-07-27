"""Bounded subprocess capture for local plugin and checker isolation.

Children run in their own process group. Reader threads cap retained output and
terminate the whole group as soon as either stream exceeds its limit. Timeouts
also terminate descendants rather than only the immediate worker.
"""

from __future__ import annotations

import os
import shutil
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


@dataclass(frozen=True, slots=True)
class ProcessResourceLimits:
    """Portable subset of operating-system worker resource limits.

    Limits are applied on POSIX platforms that expose ``resource.prlimit``.
    Other platforms retain the existing wall-time and output limits.
    """

    cpu_seconds: int | None = None
    address_space_bytes: int | None = None

    def __post_init__(self) -> None:
        if self.cpu_seconds is not None and self.cpu_seconds <= 0:
            raise ValueError("CPU limit must be positive")
        if self.address_space_bytes is not None and self.address_space_bytes <= 0:
            raise ValueError("address-space limit must be positive")


def _apply_resource_limits(
    process: subprocess.Popen[bytes],
    limits: ProcessResourceLimits,
) -> None:
    """Apply supported hard limits before accepting worker output."""

    if os.name != "posix":
        return
    try:
        import resource

        prlimit = resource.prlimit
    except (AttributeError, ImportError):  # pragma: no cover - platform dependent
        return

    def set_limit(kind: int, value: int) -> None:
        # A very short-lived child may exit between Popen and prlimit. It can
        # no longer consume resources, so there is nothing left to constrain.
        with suppress(ProcessLookupError):
            prlimit(process.pid, kind, (value, value))

    if limits.cpu_seconds is not None:
        set_limit(resource.RLIMIT_CPU, limits.cpu_seconds)
    if limits.address_space_bytes is not None:
        set_limit(resource.RLIMIT_AS, limits.address_space_bytes)


def _resource_limited_command(
    command: Sequence[str],
    limits: ProcessResourceLimits,
) -> tuple[list[str], bool]:
    """Use util-linux prlimit so limits are installed before target execution."""

    if os.name != "posix" or (prlimit := shutil.which("prlimit")) is None:
        return list(command), False
    options: list[str] = []
    if limits.cpu_seconds is not None:
        options.append(f"--cpu={limits.cpu_seconds}:{limits.cpu_seconds}")
    if limits.address_space_bytes is not None:
        options.append(
            f"--as={limits.address_space_bytes}:{limits.address_space_bytes}"
        )
    return [prlimit, *options, "--", *command], True


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
    resource_limits: ProcessResourceLimits | None = None,
) -> BoundedProcessResult:
    """Run a child with bounded output, time, lifetime, and supported resources."""

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
        bounded_command, limits_applied_before_exec = (
            _resource_limited_command(command, resource_limits)
            if resource_limits is not None
            else (list(command), False)
        )
        process = subprocess.Popen(
            bounded_command,
            stdin=stdin_file,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            start_new_session=start_new_session,
            creationflags=creationflags,
        )
        if resource_limits is not None and not limits_applied_before_exec:
            try:
                _apply_resource_limits(process, resource_limits)
            except (OSError, ValueError):
                _kill_process_tree(process)
                process.wait()
                raise
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
