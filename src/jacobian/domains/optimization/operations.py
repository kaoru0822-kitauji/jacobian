"""Bounded rational optimization operations backed by SymPy."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from pydantic import ValidationError

from jacobian.bounded_process import ProcessResourceLimits, run_bounded_process
from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.contracts.results import ContractModel, ExecutionStatus
from jacobian.contracts.validated_analysis import (
    RationalLinearProgramObligation,
    RationalLinearProgramRequest,
    RationalLinearProgramResult,
)
from jacobian.domains._examples import example
from jacobian.operations import (
    BoundedSearchIncomplete,
    BoundedSearchInterrupted,
    BoundedSearchOperation,
    BoundedSearchOutcome,
    BoundedSearchWitness,
)

_WORKER_MODULE = "jacobian.domains.optimization.worker"


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
        raise RuntimeError("rational optimization worker failed")
    value = loads_strict_json(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("rational optimization worker returned a non-object")
    return value


def _linear_program(
    request: RationalLinearProgramRequest,
) -> BoundedSearchOutcome[RationalLinearProgramResult]:
    try:
        result = RationalLinearProgramResult.model_validate(
            _run_worker(
                request.model_dump(mode="json"),
                wall_seconds=request.wall_seconds,
            )
        )
    except subprocess.TimeoutExpired:
        detail = (
            "The exact rational LP worker exceeded the declared wall-clock "
            "budget; no feasibility or optimality conclusion is available."
        )
        return BoundedSearchInterrupted(
            value=RationalLinearProgramResult(status="TIMEOUT", detail=detail),
            status=ExecutionStatus.TIMEOUT,
            diagnostic=CapabilityDiagnostic(
                code="RATIONAL_LINEAR_PROGRAM_TIMEOUT",
                stage="rational_optimization_backend",
                message=detail,
            ),
        )
    except (OSError, RuntimeError, json.JSONDecodeError, ValidationError):
        detail = (
            "The exact rational LP worker failed or returned malformed "
            "output; no feasibility or optimality conclusion is available."
        )
        return BoundedSearchInterrupted(
            value=RationalLinearProgramResult(
                status="BACKEND_ERROR",
                detail=detail,
            ),
            status=ExecutionStatus.ERROR,
            diagnostic=CapabilityDiagnostic(
                code="RATIONAL_LINEAR_PROGRAM_BACKEND_ERROR",
                stage="rational_optimization_backend",
                message=detail,
            ),
        )
    if result.status == "CERTIFICATE_PRODUCED":
        return BoundedSearchWitness(result)
    return BoundedSearchIncomplete(result)


def _scope(
    request: RationalLinearProgramRequest,
    _result: RationalLinearProgramResult,
) -> dict[str, object]:
    return {
        "variables": len(request.program.variables),
        "constraints": len(request.program.coefficients),
        "wall_seconds": request.wall_seconds,
        "standard_form": "MIN_CX; AX_EQUALS_B; X_NONNEGATIVE",
    }


def _obligation(
    request: RationalLinearProgramRequest,
    result: RationalLinearProgramResult,
) -> ContractModel:
    return RationalLinearProgramObligation(
        program=request.program,
        status=result.status,
        primal_candidate=result.primal_candidate,
        dual_candidate=result.dual_candidate,
    )


RATIONAL_LINEAR_CAPABILITIES = (
    BoundedSearchOperation(
        capability_id="optimization.linear.rational_optimum.compute",
        title="Produce a rational linear-program optimum certificate",
        description=(
            "Use bounded exact SymPy simplex calls to produce primal and dual "
            "candidates for a standard-form rational linear program."
        ),
        request_model=RationalLinearProgramRequest,
        result_model=RationalLinearProgramResult,
        implementation=_linear_program,
        relation_id="optimization.linear.rational_optimum.relation",
        scope_parameters=_scope,
        is_complete=lambda result: result.status == "CERTIFICATE_PRODUCED",
        obligation_model=RationalLinearProgramObligation,
        obligation=_obligation,
        incomplete_basis=(
            "bounded exact optimization did not produce primal and dual "
            "candidates with equal exact objective values"
        ),
        tags=(
            "optimization",
            "linear-program",
            "rational",
            "certificate",
            "bounded",
        ),
        invocation_examples=(
            example(
                "one_variable_unit_lp",
                "Optimize x subject to x=1 and x>=0.",
                {
                    "program": {
                        "variables": ["x"],
                        "objective": [{"num": "1", "den": "1"}],
                        "coefficients": [[{"num": "1", "den": "1"}]],
                        "rhs": [{"num": "1", "den": "1"}],
                    },
                    "wall_seconds": 5,
                },
            ),
        ),
    ),
)

__all__ = ["RATIONAL_LINEAR_CAPABILITIES"]
