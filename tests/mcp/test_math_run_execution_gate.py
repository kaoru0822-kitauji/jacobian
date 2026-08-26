"""MCP execution-gate cancellation and request-admission contracts."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from typing import Any, cast

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp.shared.exceptions import MCPError

from jacobian._models import StrictModel
from jacobian.catalog.catalog import Catalog
from jacobian.catalog.models import MathTool
from jacobian.mcp.runtime import AppState
from jacobian.mcp.tools import _EXECUTION_LOCK_POLL_SECONDS, math_run


class _Request(StrictModel):
    value: int


class _Result(StrictModel):
    value: int


def _context(state: AppState, cancellation: threading.Event) -> Any:
    return cast(
        Any,
        SimpleNamespace(
            request_context=SimpleNamespace(
                lifespan_context=state,
                session=SimpleNamespace(
                    _request_outbound=SimpleNamespace(cancel_requested=cancellation)
                ),
            )
        ),
    )


def test_math_run_rejects_cancelled_request_while_waiting_for_execution_gate() -> None:
    invocations: list[int] = []

    def kernel(request: _Request) -> _Result:
        invocations.append(request.value)
        return _Result(value=request.value)

    tool = MathTool(
        operation_id="test.execution_gate.cancelled",
        title="Cancelled execution gate",
        description="Records whether a cancelled request enters the kernel.",
        request_type=_Request,
        result_type=_Result,
        run=kernel,
    )
    state = AppState(operation_catalog=Catalog((tool,)))
    cancellation = threading.Event()
    context = _context(state, cancellation)
    failure: list[Exception] = []

    def call() -> None:
        try:
            math_run(
                "test.execution_gate.cancelled",
                {"value": 7},
                ctx=context,
            )
        except Exception as exc:
            failure.append(exc)

    state.execution_lock.acquire()
    try:
        worker = threading.Thread(target=call)
        worker.start()
        time.sleep(2 * _EXECUTION_LOCK_POLL_SECONDS)
        cancellation.set()
        worker.join(timeout=1)
        assert not worker.is_alive()
    finally:
        state.execution_lock.release()

    assert len(failure) == 1
    assert isinstance(failure[0], ToolError)
    assert invocations == []


def test_math_run_validates_before_acquiring_execution_gate() -> None:
    tool = MathTool(
        operation_id="test.execution_gate.validation",
        title="Execution gate validation",
        description="Validates before entering the kernel gate.",
        request_type=_Request,
        result_type=_Result,
        run=lambda request: _Result(value=request.value),
    )
    state = AppState(operation_catalog=Catalog((tool,)))
    state.execution_lock.acquire()
    try:
        with pytest.raises(MCPError, match="operation payload failed validation"):
            math_run(
                "test.execution_gate.validation",
                {"value": "invalid"},
                ctx=_context(state, threading.Event()),
            )
        assert state.execution_lock.locked()
    finally:
        state.execution_lock.release()
