"""Bounded isolated Gröbner-basis capability."""

from __future__ import annotations

import sys

from pydantic import ValidationError

from jacobian.bounded_process import ProcessResourceLimits, run_bounded_process
from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.contracts.polynomial_operations import (
    PolynomialGroebnerBasisObligation,
    PolynomialGroebnerBasisRequest,
    PolynomialGroebnerBasisResult,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.operations import (
    BoundedSearchOperation,
    BoundedSearchOutcome,
    BoundedSearchWitness,
    OperationExecutionFailure,
)

_PROTOCOL = "jacobian.polynomial.groebner.sympy.v1"
_STDOUT_LIMIT = 2_000_000
_STDERR_LIMIT = 64_000


def _failure(
    status: ExecutionStatus,
    code: str,
    message: str,
) -> OperationExecutionFailure:
    return OperationExecutionFailure(
        status=status,
        diagnostic=CapabilityDiagnostic(
            code=code,
            stage="polynomial_groebner_computation",
            message=message,
            hint="Reduce the ideal size or degree, or increase the bounded wall time.",
        ),
    )


def _compute(
    request: PolynomialGroebnerBasisRequest,
) -> BoundedSearchOutcome[PolynomialGroebnerBasisResult]:
    try:
        completed = run_bounded_process(
            [
                sys.executable,
                "-I",
                "-m",
                "jacobian.domains.polynomial.groebner_worker",
            ],
            input_bytes=canonicalize_json(
                {
                    "protocol": _PROTOCOL,
                    "request": request.model_dump(mode="json"),
                }
            ),
            timeout_seconds=float(request.resource_budget.wall_seconds),
            environment={
                "LANG": "C",
                "LC_ALL": "C",
                "TZ": "UTC",
                "PYTHONHASHSEED": "0",
            },
            stdout_limit=_STDOUT_LIMIT,
            stderr_limit=_STDERR_LIMIT,
            resource_limits=ProcessResourceLimits(
                cpu_seconds=request.resource_budget.wall_seconds + 1,
                address_space_bytes=1024 * 1024 * 1024,
            ),
        )
    except OSError:
        return _failure(
            ExecutionStatus.ERROR,
            "POLYNOMIAL_GROEBNER_WORKER_START_FAILED",
            "The isolated SymPy Gröbner worker could not be started.",
        )
    if completed.timed_out:
        return _failure(
            ExecutionStatus.TIMEOUT,
            "POLYNOMIAL_GROEBNER_TIMEOUT",
            "The Gröbner wall-clock budget expired; no partial basis was retained.",
        )
    if completed.stdout_exceeded or completed.stderr_exceeded:
        return _failure(
            ExecutionStatus.ERROR,
            "POLYNOMIAL_GROEBNER_OUTPUT_LIMIT_EXCEEDED",
            "The isolated worker exceeded its bounded output protocol.",
        )
    if completed.returncode != 0:
        return _failure(
            ExecutionStatus.ERROR,
            "POLYNOMIAL_GROEBNER_WORKER_FAILED",
            "The isolated SymPy Gröbner computation did not complete successfully.",
        )
    try:
        payload = loads_strict_json(completed.stdout)
        if not isinstance(payload, dict) or set(payload) != {"protocol", "result"}:
            raise ValueError("unexpected worker response fields")
        if payload["protocol"] != _PROTOCOL:
            raise ValueError("worker protocol does not match")
        result = PolynomialGroebnerBasisResult.model_validate(payload["result"])
    except (TypeError, ValueError, ValidationError):
        return _failure(
            ExecutionStatus.ERROR,
            "POLYNOMIAL_GROEBNER_PROTOCOL_INVALID",
            "The worker returned a result outside the bounded exact contract.",
        )
    return BoundedSearchWitness(result)


def _scope(
    request: PolynomialGroebnerBasisRequest,
    result: PolynomialGroebnerBasisResult,
) -> dict[str, object]:
    return {
        "variables": list(result.variables),
        "monomial_order": result.monomial_order,
        "generator_count": len(request.generators),
        "wall_seconds": request.resource_budget.wall_seconds,
        "maximum_basis_polynomials": (
            request.resource_budget.maximum_basis_polynomials
        ),
        "maximum_output_terms": request.resource_budget.maximum_output_terms,
    }


def _obligation(
    _request: PolynomialGroebnerBasisRequest,
    _result: PolynomialGroebnerBasisResult,
) -> PolynomialGroebnerBasisObligation:
    return PolynomialGroebnerBasisObligation()


POLYNOMIAL_GROEBNER_CAPABILITY = BoundedSearchOperation(
    capability_id="polynomial.groebner_basis.compute",
    title="Compute a bounded Gröbner basis",
    description=(
        "Compute a complete reduced monic Gröbner basis over QQ in an isolated "
        "SymPy worker under declared input, output, and wall-clock limits."
    ),
    request_model=PolynomialGroebnerBasisRequest,
    result_model=PolynomialGroebnerBasisResult,
    implementation=_compute,
    relation_id="polynomial.relation.groebner-basis-of",
    scope_parameters=_scope,
    is_complete=lambda result: result.completion == "COMPLETE",
    obligation_model=PolynomialGroebnerBasisObligation,
    obligation=_obligation,
    incomplete_basis=(
        "the bounded Gröbner computation did not complete; no partial basis "
        "supports an ideal conclusion"
    ),
    tags=("polynomial", "groebner", "ideal", "bounded", "exact"),
)

__all__ = ["POLYNOMIAL_GROEBNER_CAPABILITY"]
