"""Bounded local execution for installed plugin capabilities."""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from typing import Any

from jacobian.bounded_process import run_bounded_process
from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.contracts.results import ExecutionStatus
from jacobian.implementation import package_source_digest


@dataclass(frozen=True, slots=True)
class PluginExecutionResult:
    status: ExecutionStatus
    output: dict[str, Any] | None
    diagnostics: str
    detail: str | None
    runtime_ms: int


class PluginExecutor:
    """Run an installed capability out of process with fail-closed outcomes."""

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
        started = time.monotonic()
        expected_digest = implementation_digest or package_source_digest(entrypoint)
        environment = dict(os.environ)
        environment.update({"PYTHONHASHSEED": "0", "TZ": "UTC"})
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
                detail="plugin execution timed out",
                runtime_ms=_elapsed_ms(started),
            )

        if completed.stdout_exceeded:
            return PluginExecutionResult(
                status=ExecutionStatus.ERROR,
                output=None,
                diagnostics=diagnostics,
                detail="plugin output exceeds the configured limit",
                runtime_ms=_elapsed_ms(started),
            )
        if completed.stderr_exceeded:
            return PluginExecutionResult(
                status=ExecutionStatus.ERROR,
                output=None,
                diagnostics=diagnostics,
                detail="plugin diagnostics exceed the configured limit",
                runtime_ms=_elapsed_ms(started),
            )
        try:
            output = loads_strict_json(completed.stdout)
        except ValueError:
            return PluginExecutionResult(
                status=ExecutionStatus.ERROR,
                output=None,
                diagnostics=diagnostics,
                detail="plugin returned invalid JSON",
                runtime_ms=_elapsed_ms(started),
            )
        if completed.returncode != 0:
            detail = (
                output.get("detail", "plugin execution failed")
                if isinstance(output, dict)
                else "plugin execution failed"
            )
            return PluginExecutionResult(
                status=ExecutionStatus.ERROR,
                output=None,
                diagnostics=diagnostics,
                detail=str(detail),
                runtime_ms=_elapsed_ms(started),
            )
        if not isinstance(output, dict):
            return PluginExecutionResult(
                status=ExecutionStatus.ERROR,
                output=None,
                diagnostics=diagnostics,
                detail="plugin response must be a JSON object",
                runtime_ms=_elapsed_ms(started),
            )
        if output.get("measured_implementation_digest") != expected_digest:
            return PluginExecutionResult(
                status=ExecutionStatus.ERROR,
                output=None,
                diagnostics=diagnostics,
                detail="plugin worker did not execute the resolved implementation",
                runtime_ms=_elapsed_ms(started),
            )
        response = output.get("response")
        if not isinstance(response, dict):
            return PluginExecutionResult(
                status=ExecutionStatus.ERROR,
                output=None,
                diagnostics=diagnostics,
                detail="plugin response must be a JSON object",
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


def _bounded_text(value: bytes | str | None, *, limit: int) -> str:
    if value is None:
        return ""
    raw = value.encode("utf-8", errors="replace") if isinstance(value, str) else value
    return raw[:limit].decode("utf-8", errors="replace")
