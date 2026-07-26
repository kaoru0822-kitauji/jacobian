"""Maintained-backend implementations for validated-analysis operations."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from flint import fmpq
from pydantic import ValidationError

from jacobian.bounded_process import run_bounded_process
from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.results import ContractModel, ExecutionStatus
from jacobian.contracts.validated_analysis import (
    ArbPointEnclosureObligation,
    ArbPointEnclosureRequest,
    ArbPointEnclosureResult,
    FiniteRawMomentContribution,
    FiniteRawMomentRequest,
    FiniteRawMomentResult,
    RationalLinearProgramObligation,
    RationalLinearProgramRequest,
    RationalLinearProgramResult,
)
from jacobian.operations import (
    BoundedSearchIncomplete,
    BoundedSearchInterrupted,
    BoundedSearchOperation,
    BoundedSearchOutcome,
    BoundedSearchWitness,
    ComputedOperation,
    ComputedOutcome,
    ComputedSuccess,
)

_WORKER_MODULE = "jacobian.domains.validated_analysis.worker"
_STDOUT_LIMIT = 2_000_000
_STDERR_LIMIT = 64_000


def _interruption_diagnostic(
    *,
    code: str,
    stage: str,
    message: str,
) -> CapabilityDiagnostic:
    return CapabilityDiagnostic(
        code=code,
        stage=stage,
        message=message,
    )


def _run_worker(
    operation: str,
    payload: dict[str, Any],
    *,
    wall_seconds: int,
) -> dict[str, Any]:
    command = [sys.executable, "-I", "-m", _WORKER_MODULE]
    completed = run_bounded_process(
        command,
        input_bytes=canonicalize_json(
            {"operation": operation, "payload": payload}
        ),
        timeout_seconds=float(wall_seconds),
        environment={
            "LANG": "C",
            "LC_ALL": "C",
            "TZ": "UTC",
            "PYTHONHASHSEED": "0",
        },
        stdout_limit=_STDOUT_LIMIT,
        stderr_limit=_STDERR_LIMIT,
    )
    if completed.timed_out:
        raise subprocess.TimeoutExpired(command, wall_seconds)
    if (
        completed.returncode != 0
        or completed.stdout_exceeded
        or completed.stderr_exceeded
    ):
        raise RuntimeError("validated-analysis backend worker failed")
    value = loads_strict_json(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("validated-analysis backend returned a non-object")
    return value


def _arb_point_enclosure(
    request: ArbPointEnclosureRequest,
) -> BoundedSearchOutcome[ArbPointEnclosureResult]:
    base = {
        "function": request.function.value,
        "argument": request.argument.model_dump(mode="json"),
        "precision_bits": request.precision_bits,
    }
    try:
        payload = _run_worker(
            "arb_point",
            request.model_dump(mode="json", exclude={"wall_seconds"}),
            wall_seconds=request.wall_seconds,
        )
        status = payload.get("status")
        if status == "ENCLOSED":
            result = ArbPointEnclosureResult.model_validate(
                {
                    **base,
                    **payload,
                    "detail": (
                        "Pinned Arb ball arithmetic returned an outward-rounded "
                        "enclosure with exact dyadic endpoints."
                    ),
                }
            )
            return BoundedSearchWitness(result)
        if status == "NONFINITE":
            return BoundedSearchIncomplete(
                ArbPointEnclosureResult.model_validate(
                    {
                        **base,
                        "status": "NONFINITE",
                        "detail": (
                            "Arb returned a non-finite ball for this function and "
                            "argument; no enclosure conclusion is available."
                        ),
                    }
                )
            )
        raise RuntimeError("validated-analysis backend returned an unknown status")
    except subprocess.TimeoutExpired:
        detail = (
            "The Arb worker exceeded the declared wall-clock budget; "
            "no enclosure conclusion is available."
        )
        return BoundedSearchInterrupted(
            value=ArbPointEnclosureResult.model_validate(
                {
                    **base,
                    "status": "TIMEOUT",
                    "detail": detail,
                }
            ),
            status=ExecutionStatus.TIMEOUT,
            diagnostic=_interruption_diagnostic(
                code="ARB_POINT_ENCLOSURE_TIMEOUT",
                stage="validated_analysis_backend",
                message=detail,
            ),
        )
    except (OSError, RuntimeError, json.JSONDecodeError, ValidationError):
        detail = (
            "The Arb worker failed or returned malformed output; "
            "no enclosure conclusion is available."
        )
        return BoundedSearchInterrupted(
            value=ArbPointEnclosureResult.model_validate(
                {
                    **base,
                    "status": "BACKEND_ERROR",
                    "detail": detail,
                }
            ),
            status=ExecutionStatus.ERROR,
            diagnostic=_interruption_diagnostic(
                code="ARB_POINT_ENCLOSURE_BACKEND_ERROR",
                stage="validated_analysis_backend",
                message=detail,
            ),
        )


def _arb_scope(
    request: ArbPointEnclosureRequest,
    _result: ArbPointEnclosureResult,
) -> dict[str, object]:
    return {
        "function": request.function.value,
        "precision_bits": request.precision_bits,
        "wall_seconds": request.wall_seconds,
    }


def _arb_obligation(
    request: ArbPointEnclosureRequest,
    result: ArbPointEnclosureResult,
) -> ContractModel:
    return ArbPointEnclosureObligation(
        function=request.function,
        argument=request.argument,
        precision_bits=request.precision_bits,
        claimed_lower=result.lower,
        claimed_upper=result.upper,
        status=result.status,
    )


ARB_POINT_ENCLOSURE_CAPABILITY = BoundedSearchOperation(
    capability_id="analysis.real_function.point_enclosure.compute",
    title="Enclose a real function at a rational point",
    description=(
        "Use pinned Arb ball arithmetic to enclose one fixed supported real "
        "function at one exact rational point within a wall-clock budget."
    ),
    request_model=ArbPointEnclosureRequest,
    result_model=ArbPointEnclosureResult,
    implementation=_arb_point_enclosure,
    relation_id="analysis.real_function.point_enclosure.relation",
    scope_parameters=_arb_scope,
    is_complete=lambda result: result.status == "ENCLOSED",
    obligation_model=ArbPointEnclosureObligation,
    obligation=_arb_obligation,
    incomplete_basis=(
        "the backend returned no finite enclosure or did not complete within "
        "the declared bounded execution"
    ),
    tags=("analysis", "validated", "arb", "enclosure", "bounded"),
)


def _fmpq(value: CanonicalRational) -> fmpq:
    return fmpq(int(value.num), int(value.den))


def _wire_fmpq(value: fmpq) -> CanonicalRational:
    return CanonicalRational(num=str(value.p), den=str(value.q))


def _raw_moment(
    request: FiniteRawMomentRequest,
) -> ComputedOutcome[FiniteRawMomentResult]:
    contributions: list[FiniteRawMomentContribution] = []
    total = fmpq(0)
    for atom in request.atoms:
        value = _fmpq(atom.value)
        probability = _fmpq(atom.probability)
        powered = value**request.order
        contribution = probability * powered
        total += contribution
        contributions.append(
            FiniteRawMomentContribution(
                value=atom.value,
                probability=atom.probability,
                powered_value=_wire_fmpq(powered),
                contribution=_wire_fmpq(contribution),
            )
        )
    return ComputedSuccess(
        FiniteRawMomentResult(
            order=request.order,
            moment=_wire_fmpq(total),
            contributions=tuple(contributions),
        )
    )


FINITE_RAW_MOMENT_CAPABILITY = ComputedOperation(
    capability_id="probability.finite_distribution.raw_moment.compute",
    title="Exact finite-distribution raw moment",
    description=(
        "Compute one bounded raw moment of a normalized finite exact rational "
        "distribution, preserving every exact atom contribution."
    ),
    request_model=FiniteRawMomentRequest,
    result_model=FiniteRawMomentResult,
    implementation=_raw_moment,
    relation_id="probability.finite_distribution.raw_moment.relation",
    tags=("probability", "moment", "finite", "exact", "python-flint"),
)


def _linear_program(
    request: RationalLinearProgramRequest,
) -> BoundedSearchOutcome[RationalLinearProgramResult]:
    try:
        payload = _run_worker(
            "linear_program",
            request.model_dump(mode="json", exclude={"wall_seconds"}),
            wall_seconds=request.wall_seconds,
        )
        result = RationalLinearProgramResult.model_validate(payload)
    except subprocess.TimeoutExpired:
        detail = (
            "The exact rational LP worker exceeded the declared wall-clock "
            "budget; no feasibility or optimality conclusion is available."
        )
        result = RationalLinearProgramResult(
            status="TIMEOUT",
            detail=detail,
        )
        return BoundedSearchInterrupted(
            value=result,
            status=ExecutionStatus.TIMEOUT,
            diagnostic=_interruption_diagnostic(
                code="RATIONAL_LINEAR_PROGRAM_TIMEOUT",
                stage="validated_optimization_backend",
                message=detail,
            ),
        )
    except (OSError, RuntimeError, json.JSONDecodeError, ValidationError):
        detail = (
            "The exact rational LP worker failed or returned malformed "
            "output; no feasibility or optimality conclusion is available."
        )
        result = RationalLinearProgramResult(
            status="BACKEND_ERROR",
            detail=detail,
        )
        return BoundedSearchInterrupted(
            value=result,
            status=ExecutionStatus.ERROR,
            diagnostic=_interruption_diagnostic(
                code="RATIONAL_LINEAR_PROGRAM_BACKEND_ERROR",
                stage="validated_optimization_backend",
                message=detail,
            ),
        )
    if result.status == "CERTIFICATE_PRODUCED":
        return BoundedSearchWitness(result)
    return BoundedSearchIncomplete(result)


def _linear_program_scope(
    request: RationalLinearProgramRequest,
    _result: RationalLinearProgramResult,
) -> dict[str, object]:
    return {
        "variables": len(request.program.variables),
        "constraints": len(request.program.coefficients),
        "wall_seconds": request.wall_seconds,
        "standard_form": "MIN_CX; AX_EQUALS_B; X_NONNEGATIVE",
    }


def _linear_program_obligation(
    request: RationalLinearProgramRequest,
    result: RationalLinearProgramResult,
) -> ContractModel:
    return RationalLinearProgramObligation(
        program=request.program,
        status=result.status,
        primal_candidate=result.primal_candidate,
        dual_candidate=result.dual_candidate,
    )


RATIONAL_LP_CAPABILITY = BoundedSearchOperation(
    capability_id="optimization.linear.rational_optimum.compute",
    title="Produce a rational linear-program optimum certificate",
    description=(
        "Use bounded exact SymPy simplex calls to produce primal and dual "
        "candidates for one standard-form rational linear program."
    ),
    request_model=RationalLinearProgramRequest,
    result_model=RationalLinearProgramResult,
    implementation=_linear_program,
    relation_id="optimization.linear.rational_optimum.relation",
    scope_parameters=_linear_program_scope,
    is_complete=lambda result: result.status == "CERTIFICATE_PRODUCED",
    obligation_model=RationalLinearProgramObligation,
    obligation=_linear_program_obligation,
    incomplete_basis=(
        "bounded exact optimization did not produce both primal and dual "
        "candidates with equal exact objective values"
    ),
    tags=("optimization", "linear-program", "rational", "certificate", "bounded"),
)


VALIDATED_ANALYSIS_CAPABILITIES = (
    ARB_POINT_ENCLOSURE_CAPABILITY,
    FINITE_RAW_MOMENT_CAPABILITY,
    RATIONAL_LP_CAPABILITY,
)

__all__ = ["VALIDATED_ANALYSIS_CAPABILITIES"]
