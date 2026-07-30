"""Fixtures that own real external boundaries.

The boundary tier is the only place where tests may deliberately start a
child process, inspect an optional provider, or open a durability-focused
SQLite store.  Fixtures are function scoped unless the value is an immutable
provider identity.  Process fixtures expose launchers so a test can choose the
exact command while teardown still owns every child it started.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from jacobian.contracts.capabilities import (
    CapabilityProviderAvailability,
    CapabilityProviderRuntime,
)
from jacobian.store import ArtifactStore

pytest_plugins = ("tests.support.runtime_fixtures",)


@dataclass
class ManagedProcess:
    """A child process whose process group is owned by one test."""

    process: subprocess.Popen[Any]

    @property
    def pid(self) -> int:
        return self.process.pid

    def terminate(self) -> None:
        """Terminate the process and descendants, then reap the child."""

        if self.process.poll() is not None:
            return
        if os.name == "posix":
            with suppress(ProcessLookupError, OSError):
                os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=2)
                return
            except subprocess.TimeoutExpired:
                with suppress(ProcessLookupError, OSError):
                    os.killpg(self.process.pid, signal.SIGKILL)
        else:  # pragma: no cover - exercised by Windows CI
            self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            self.process.kill()
            self.process.wait(timeout=5)


@dataclass
class MCPServerProcess(ManagedProcess):
    """A running streamable-HTTP MCP endpoint and its private state root."""

    host: str
    port: int
    state_dir: Path

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/mcp"


def _terminate_all(children: list[ManagedProcess]) -> None:
    for child in reversed(children):
        child.terminate()


def _start_process(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> ManagedProcess:
    process = subprocess.Popen(
        list(command),
        cwd=cwd,
        env=dict(environment) if environment is not None else None,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=os.name == "posix",
        creationflags=(
            int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            if os.name == "nt"
            else 0
        ),
    )
    return ManagedProcess(process)


@pytest.fixture
def durable_store(tmp_path: Path) -> Iterator[ArtifactStore]:
    """Open one test-owned SQLite store for durability and recovery claims."""

    store = ArtifactStore(tmp_path / "state")
    try:
        yield store
    finally:
        store.close()


@pytest.fixture
def checker_process() -> Iterator[Callable[[Sequence[str]], ManagedProcess]]:
    """Return a launcher for a checker child with process-group teardown."""

    children: list[ManagedProcess] = []

    def launch(command: Sequence[str]) -> ManagedProcess:
        child = _start_process(command)
        children.append(child)
        return child

    try:
        yield launch
    finally:
        _terminate_all(children)


def _unused_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _wait_for_port(
    process: ManagedProcess,
    host: str,
    port: int,
    *,
    timeout_seconds: float = 30,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if process.process.poll() is not None:
            stderr = process.process.stderr
            detail = stderr.read().decode(errors="replace") if stderr else ""
            raise RuntimeError(
                f"MCP server exited before binding port {port}: {detail[-2_000:]}"
            )
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError(f"MCP server did not bind {host}:{port} before the deadline")


@pytest.fixture
def mcp_server_process(
    tmp_path: Path,
) -> Iterator[Callable[..., MCPServerProcess]]:
    """Return a launcher for an isolated streamable-HTTP MCP server."""

    children: list[ManagedProcess] = []

    def launch(*, host: str = "127.0.0.1", port: int | None = None) -> MCPServerProcess:
        selected_port = _unused_port() if port is None else port
        state_dir = tmp_path / "mcp-state"
        command = [
            sys.executable,
            "-m",
            "jacobian.adapters.mcp.cli",
            "--transport",
            "streamable-http",
            "--host",
            host,
            "--port",
            str(selected_port),
            "--state-dir",
            str(state_dir),
            "--allow-anonymous",
        ]
        child = _start_process(command)
        children.append(child)
        endpoint = MCPServerProcess(
            process=child.process,
            host=host,
            port=selected_port,
            state_dir=state_dir,
        )
        try:
            _wait_for_port(endpoint, host, selected_port)
        except BaseException:
            endpoint.terminate()
            raise
        return endpoint

    try:
        yield launch
    finally:
        _terminate_all(children)


def _require_available(
    runtime: CapabilityProviderRuntime,
    *,
    name: str,
) -> CapabilityProviderRuntime:
    if runtime.availability is not CapabilityProviderAvailability.AVAILABLE:
        pytest.skip(runtime.diagnostic or f"{name} provider is unavailable")
    return runtime


def _require_python_attributes(
    runtime: CapabilityProviderRuntime,
    *,
    name: str,
) -> CapabilityProviderRuntime:
    """Complete the production identity probe with a callable API check."""

    import importlib

    import_name = runtime.distribution_import_name
    if not import_name:
        pytest.skip(f"{name} provider did not publish an import target")
    try:
        module = importlib.import_module(import_name)
        missing = [
            attribute
            for attribute in runtime.distribution_required_attributes
            if not hasattr(module, attribute)
        ]
    except (ImportError, OSError) as exc:
        pytest.skip(f"{name} provider failed its callable readiness check: {exc}")
    if missing:
        pytest.skip(f"{name} provider is missing required attributes: {missing}")
    return runtime


@pytest.fixture(scope="session")
def available_cvc5() -> CapabilityProviderRuntime:
    """Return the exact usable cvc5 runtime, or skip closed."""

    from jacobian.provider_runtime import cvc5_provider_runtime

    runtime = _require_available(cvc5_provider_runtime(), name="cvc5")
    return _require_python_attributes(runtime, name="cvc5")


@pytest.fixture(scope="session")
def available_flint() -> CapabilityProviderRuntime:
    """Return the exact usable Python-FLINT runtime, or skip closed."""

    from jacobian.provider_runtime import python_flint_provider_runtime

    runtime = _require_available(
        python_flint_provider_runtime(refresh=True),
        name="python-flint",
    )
    return _require_python_attributes(runtime, name="python-flint")


@pytest.fixture(scope="session")
def available_lean() -> CapabilityProviderRuntime:
    """Return the pinned Lean/Mathlib runtime, or skip closed."""

    from jacobian.provider_runtime import lean_provider_runtime

    return _require_available(
        lean_provider_runtime(
            profiles={"mathlib": {"mathlib_commit": "pinned"}},
            checker_ids=("lean.mathlib",),
        ),
        name="Lean/Mathlib",
    )


@pytest.fixture(scope="session")
def available_external_sat() -> tuple[CapabilityProviderRuntime, ...]:
    """Return the complete pinned external SAT toolchain, or skip closed."""

    from jacobian.provider_runtime import (
        cadical_provider_runtime,
        carcara_provider_runtime,
        drat_trim_provider_runtime,
    )

    runtimes = (
        cadical_provider_runtime(),
        drat_trim_provider_runtime(),
        carcara_provider_runtime(),
    )
    unavailable = tuple(
        runtime
        for runtime in runtimes
        if runtime.availability is not CapabilityProviderAvailability.AVAILABLE
    )
    if unavailable:
        detail = "; ".join(
            runtime.diagnostic or runtime.provider for runtime in unavailable
        )
        pytest.skip(f"external SAT toolchain is unavailable: {detail}")
    return runtimes
