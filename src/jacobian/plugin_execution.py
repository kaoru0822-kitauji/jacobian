"""Bounded local execution for installed plugin capabilities."""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from typing import Any

from jacobian.bounded_process import run_bounded_process
from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.contracts.results import ExecutionStatus
from jacobian.implementation import package_source_digest
from jacobian.worker_environment import worker_environment

_LOGGER = logging.getLogger(__name__)

_PLUGIN_TIMEOUT = (
    "The plugin did not finish within the allowed time. "
    "Retry with a larger time budget or a smaller request."
)
_PLUGIN_OUTPUT_TOO_LARGE = (
    "The plugin returned too much data. Retry with a smaller request."
)
_PLUGIN_DIAGNOSTICS_TOO_LARGE = (
    "The plugin produced too many diagnostics. Retry with a smaller request "
    "and inspect the local plugin log if the limit is reached again."
)
_PLUGIN_UNREADABLE_RESPONSE = (
    "The plugin returned an unreadable response. Retry once; "
    "if it happens again, inspect the local plugin log."
)
_PLUGIN_CHANGED = (
    "The plugin changed after it was registered. "
    "Reload Jacobian to register the current plugin version, then retry."
)
_PLUGIN_STOPPED = (
    "The plugin stopped before returning a result. Retry once; "
    "if it happens again, inspect the local plugin log."
)


@dataclass(frozen=True, slots=True)
class PluginExecutionResult:
    """Operational result from one local plugin worker invocation."""

    status: ExecutionStatus
    output: dict[str, Any] | None
    diagnostics: str
    detail: str | None
    runtime_ms: int


class PluginExecutor:
    """Run operator-installed local code with bounded, fail-closed outcomes.

    The child-process boundary limits elapsed time, output, and descendant
    lifetime. It is not a security sandbox and does not make plugin results
    mathematically trusted.
    """

    def __init__(
        self,
        *,
        max_output_bytes: int = 4 * 1024 * 1024,
        max_diagnostic_bytes: int = 1024 * 1024,
    ) -> None:
        self.max_output_bytes = max_output_bytes
        self.max_diagnostic_bytes = max_diagnostic_bytes

    def run(
        self,
        *,
        entrypoint: str,
        implementation_digest: str | None = None,
        request: dict[str, Any],
        timeout_seconds: float,
    ) -> PluginExecutionResult:
        """Execute a capability only if the worker measures the expected source."""

        started = time.monotonic()
        expected_digest = implementation_digest or package_source_digest(entrypoint)
        environment = worker_environment()
        completed = run_bounded_process(
            [
                sys.executable,
                "-m",
                "jacobian.plugin_worker",
                entrypoint,
                expected_digest,
            ],
            input_bytes=canonicalize_json(request),
            timeout_seconds=timeout_seconds,
            environment=environment,
            stdout_limit=self.max_output_bytes,
            stderr_limit=self.max_diagnostic_bytes,
        )
        diagnostics = _bounded_text(
            completed.stderr,
            limit=self.max_diagnostic_bytes,
        )
        if completed.timed_out:
            diagnostics = _bounded_text(
                completed.stderr,
                limit=self.max_diagnostic_bytes,
            )
            return PluginExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                output=None,
                diagnostics=diagnostics,
                detail=_PLUGIN_TIMEOUT,
                runtime_ms=_elapsed_ms(started),
            )

        if completed.stdout_exceeded:
            return PluginExecutionResult(
                status=ExecutionStatus.ERROR,
                output=None,
                diagnostics=diagnostics,
                detail=_PLUGIN_OUTPUT_TOO_LARGE,
                runtime_ms=_elapsed_ms(started),
            )
        if completed.stderr_exceeded:
            return PluginExecutionResult(
                status=ExecutionStatus.ERROR,
                output=None,
                diagnostics=diagnostics,
                detail=_PLUGIN_DIAGNOSTICS_TOO_LARGE,
                runtime_ms=_elapsed_ms(started),
            )
        try:
            output = loads_strict_json(completed.stdout)
        except ValueError:
            return PluginExecutionResult(
                status=ExecutionStatus.ERROR,
                output=None,
                diagnostics=diagnostics,
                detail=_PLUGIN_UNREADABLE_RESPONSE,
                runtime_ms=_elapsed_ms(started),
            )
        if completed.returncode != 0:
            _LOGGER.warning(
                "plugin worker stopped: response=%r diagnostics=%s",
                output,
                diagnostics,
            )
            return PluginExecutionResult(
                status=ExecutionStatus.ERROR,
                output=None,
                diagnostics=diagnostics,
                detail=_plugin_failure_detail(output),
                runtime_ms=_elapsed_ms(started),
            )
        if not isinstance(output, dict):
            return PluginExecutionResult(
                status=ExecutionStatus.ERROR,
                output=None,
                diagnostics=diagnostics,
                detail=_PLUGIN_UNREADABLE_RESPONSE,
                runtime_ms=_elapsed_ms(started),
            )
        if output.get("measured_implementation_digest") != expected_digest:
            _LOGGER.warning(
                "plugin worker measured an unexpected implementation: %r",
                output,
            )
            return PluginExecutionResult(
                status=ExecutionStatus.ERROR,
                output=None,
                diagnostics=diagnostics,
                detail=_PLUGIN_CHANGED,
                runtime_ms=_elapsed_ms(started),
            )
        response = output.get("response")
        if not isinstance(response, dict):
            return PluginExecutionResult(
                status=ExecutionStatus.ERROR,
                output=None,
                diagnostics=diagnostics,
                detail=_PLUGIN_UNREADABLE_RESPONSE,
                runtime_ms=_elapsed_ms(started),
            )
        return PluginExecutionResult(
            status=ExecutionStatus.COMPLETED,
            output=response,
            diagnostics=diagnostics,
            detail=None,
            runtime_ms=_elapsed_ms(started),
        )


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _plugin_failure_detail(output: Any) -> str:
    if isinstance(output, dict) and output.get("error_code") == "SOURCE_CHANGED":
        return _PLUGIN_CHANGED
    return _PLUGIN_STOPPED


def _bounded_text(value: bytes | str | None, *, limit: int) -> str:
    if value is None:
        return ""
    raw = value.encode("utf-8", errors="replace") if isinstance(value, str) else value
    if len(raw) <= limit:
        selected = raw
    else:
        marker = b"\n...[truncated]"
        selected = raw[: max(0, limit - len(marker))] + marker[:limit]
    return selected.decode("utf-8", errors="replace")
