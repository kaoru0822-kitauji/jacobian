"""Validated real-function operations backed by Arb."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from pydantic import ValidationError

from jacobian.bounded_process import ProcessResourceLimits, run_bounded_process
from jacobian.canonical import (
    CanonicalizationError,
    canonicalize_json,
    loads_strict_json,
)
from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.contracts.results import ExecutionStatus
from jacobian.contracts.validated_analysis import (
    ArbPointEnclosureObligation,
    ArbPointEnclosureRequest,
    ArbPointEnclosureResult,
)
from jacobian.domains._examples import example
from jacobian.operations import (
    BoundedSearchIncomplete,
    BoundedSearchInterrupted,
    BoundedSearchOperation,
    BoundedSearchOutcome,
    BoundedSearchWitness,
)

_WORKER_MODULE = "jacobian.domains.analysis.worker"


def _run_worker(payload: dict[str, Any], *, wall_seconds: int) -> dict[str, Any]:
    command = [sys.executable, "-I", "-m", _WORKER_MODULE]
    completed = run_bounded_process(
        command,
        input_bytes=canonicalize_json(payload),
        timeout_seconds=float(wall_seconds),
        environment={
            "LANG": "C",
            "LC_ALL": "C",
            "TZ": "UTC",
            "PYTHONHASHSEED": "0",
        },
        stdout_limit=2_000_000,
        stderr_limit=64_000,
        resource_limits=ProcessResourceLimits(
            cpu_seconds=wall_seconds + 1,
            address_space_bytes=1024 * 1024 * 1024,
        ),
    )
    if completed.timed_out:
        raise subprocess.TimeoutExpired(command, wall_seconds)
    if (
        completed.returncode != 0
        or completed.stdout_exceeded
        or completed.stderr_exceeded
    ):
        raise RuntimeError("Arb point-enclosure worker failed")
    value = loads_strict_json(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("Arb point-enclosure worker returned a non-object")
    return value


def _diagnostic(code: str, message: str) -> CapabilityDiagnostic:
    return CapabilityDiagnostic(
        code=code,
        stage="validated_analysis_backend",
        message=message,
    )


def _point_enclosure(
    request: ArbPointEnclosureRequest,
) -> BoundedSearchOutcome[ArbPointEnclosureResult]:
    base = {
        "function": request.function.value,
        "argument": request.argument.model_dump(mode="json"),
        "precision_bits": request.precision_bits,
    }
    try:
        payload = _run_worker(
            request.model_dump(mode="json", exclude={"wall_seconds"}),
            wall_seconds=request.wall_seconds,
        )
        if payload.get("status") == "ENCLOSED":
            return BoundedSearchWitness(
                ArbPointEnclosureResult.model_validate(
                    {
                        **base,
                        **payload,
                        "detail": (
                            "Pinned Arb ball arithmetic returned an "
                            "outward-rounded enclosure with exact dyadic endpoints."
                        ),
                    }
                )
            )
        if payload.get("status") == "NONFINITE":
            return BoundedSearchIncomplete(
                ArbPointEnclosureResult.model_validate(
                    {
                        **base,
                        "status": "NONFINITE",
                        "detail": (
                            "Arb returned a non-finite ball; no enclosure "
                            "conclusion is available."
                        ),
                    }
                )
            )
        raise RuntimeError("Arb worker returned an unknown status")
    except subprocess.TimeoutExpired:
        detail = (
            "The Arb worker exceeded the declared wall-clock budget; "
            "no enclosure conclusion is available."
        )
        return BoundedSearchInterrupted(
            value=ArbPointEnclosureResult.model_validate(
                {**base, "status": "TIMEOUT", "detail": detail}
            ),
            status=ExecutionStatus.TIMEOUT,
            diagnostic=_diagnostic("ARB_POINT_ENCLOSURE_TIMEOUT", detail),
        )
    except (OSError, RuntimeError, CanonicalizationError, ValidationError):
        detail = (
            "The Arb worker failed or returned malformed output; "
            "no enclosure conclusion is available."
        )
        return BoundedSearchInterrupted(
            value=ArbPointEnclosureResult.model_validate(
                {**base, "status": "BACKEND_ERROR", "detail": detail}
            ),
            status=ExecutionStatus.ERROR,
            diagnostic=_diagnostic("ARB_POINT_ENCLOSURE_BACKEND_ERROR", detail),
        )


def _scope(
    request: ArbPointEnclosureRequest,
    _result: ArbPointEnclosureResult,
) -> dict[str, object]:
    return {
        "function": request.function.value,
        "precision_bits": request.precision_bits,
        "wall_seconds": request.wall_seconds,
    }


def _obligation(
    request: ArbPointEnclosureRequest,
    result: ArbPointEnclosureResult,
) -> ArbPointEnclosureObligation:
    return ArbPointEnclosureObligation(
        function=request.function,
        argument=request.argument,
        precision_bits=request.precision_bits,
        claimed_lower=result.lower,
        claimed_upper=result.upper,
        status=result.status,
    )


POINT_ENCLOSURE_CAPABILITIES = (
    BoundedSearchOperation(
        capability_id="analysis.real_function.point_enclosure.compute",
        title="Enclose a real function at a rational point",
        description=(
            "Use pinned Arb ball arithmetic to enclose one supported real "
            "function at one exact rational point within a wall-clock budget."
        ),
        request_model=ArbPointEnclosureRequest,
        result_model=ArbPointEnclosureResult,
        implementation=_point_enclosure,
        relation_id="analysis.real_function.point_enclosure.relation",
        scope_parameters=_scope,
        is_complete=lambda result: result.status == "ENCLOSED",
        obligation_model=ArbPointEnclosureObligation,
        obligation=_obligation,
        incomplete_basis=(
            "Arb returned no finite enclosure or did not complete within "
            "the declared bounded execution"
        ),
        tags=("analysis", "validated", "arb", "enclosure", "bounded"),
        invocation_examples=(
            example(
                "sqrt_zero",
                "Enclose sqrt(0) at 32-bit precision.",
                {
                    "function": "SQRT",
                    "argument": {"num": "0", "den": "1"},
                    "precision_bits": 32,
                    "wall_seconds": 1,
                },
            ),
        ),
    ),
)

__all__ = ["POINT_ENCLOSURE_CAPABILITIES"]
