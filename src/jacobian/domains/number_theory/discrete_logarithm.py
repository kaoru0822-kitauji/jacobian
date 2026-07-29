"""Wall-bounded isolated SymPy discrete-logarithm operation."""

from __future__ import annotations

import sys

from pydantic import ValidationError

from jacobian.bounded_process import ProcessResourceLimits, run_bounded_process
from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.contracts.number_theory import (
    DiscreteLogarithmObligation,
    DiscreteLogarithmRequest,
    DiscreteLogarithmResult,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.domains._examples import example
from jacobian.operations import (
    BoundedSearchOperation,
    BoundedSearchOutcome,
    BoundedSearchWitness,
    OperationExecutionFailure,
)

_PROTOCOL = "jacobian.number-theory.discrete-logarithm.sympy.v1"
_STDOUT_LIMIT = 64_000
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
            stage="discrete_logarithm_computation",
            message=message,
            hint="Reduce the modulus or increase the bounded wall time.",
        ),
    )


def _compute(
    request: DiscreteLogarithmRequest,
) -> BoundedSearchOutcome[DiscreteLogarithmResult]:
    command = [
        sys.executable,
        "-I",
        "-m",
        "jacobian.domains.number_theory.discrete_logarithm_worker",
    ]
    try:
        completed = run_bounded_process(
            command,
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
            "DISCRETE_LOGARITHM_WORKER_START_FAILED",
            "The isolated SymPy discrete-logarithm worker could not be started.",
        )
    if completed.timed_out:
        return _failure(
            ExecutionStatus.TIMEOUT,
            "DISCRETE_LOGARITHM_TIMEOUT",
            "The discrete-logarithm wall-clock budget expired; no conclusion is available.",
        )
    if completed.stdout_exceeded or completed.stderr_exceeded:
        return _failure(
            ExecutionStatus.ERROR,
            "DISCRETE_LOGARITHM_OUTPUT_LIMIT_EXCEEDED",
            "The isolated worker exceeded its bounded output protocol.",
        )
    if completed.returncode != 0:
        return _failure(
            ExecutionStatus.ERROR,
            "DISCRETE_LOGARITHM_WORKER_FAILED",
            "The isolated SymPy discrete-logarithm computation failed.",
        )
    try:
        payload = loads_strict_json(completed.stdout)
        if not isinstance(payload, dict) or set(payload) != {"protocol", "result"}:
            raise ValueError("unexpected worker response fields")
        if payload["protocol"] != _PROTOCOL:
            raise ValueError("worker protocol does not match")
        result = DiscreteLogarithmResult.model_validate(payload["result"])
    except (TypeError, ValueError, ValidationError):
        return _failure(
            ExecutionStatus.ERROR,
            "DISCRETE_LOGARITHM_PROTOCOL_INVALID",
            "The worker returned a result outside the bounded exact contract.",
        )
    return BoundedSearchWitness(result)


def _scope(
    request: DiscreteLogarithmRequest,
    _result: DiscreteLogarithmResult,
) -> dict[str, object]:
    return {
        "modulus": request.modulus,
        "wall_seconds": request.resource_budget.wall_seconds,
    }


def _obligation(
    _request: DiscreteLogarithmRequest,
    result: DiscreteLogarithmResult,
) -> DiscreteLogarithmObligation:
    return DiscreteLogarithmObligation(
        base=result.base,
        target=result.target,
        modulus=result.modulus,
        status=result.status,
        discrete_log=result.discrete_log,
        required_checks=(
            ("DISCRETE_LOG_WITNESS_REPLAY",)
            if result.status == "SOLVED"
            else ("DISCRETE_LOG_NONSOLVABILITY",)
        ),
    )


DISCRETE_LOGARITHM_CAPABILITY = BoundedSearchOperation(
    capability_id="modular.compute.discrete_logarithm",
    title="Compute a bounded discrete logarithm",
    description=(
        "Compute a modular discrete logarithm with SymPy in an isolated "
        "wall-bounded worker. Timeout and worker failure are non-conclusions."
    ),
    request_model=DiscreteLogarithmRequest,
    result_model=DiscreteLogarithmResult,
    implementation=_compute,
    relation_id="modular.relation.discrete_logarithm",
    scope_parameters=_scope,
    is_complete=lambda _result: True,
    obligation_model=DiscreteLogarithmObligation,
    obligation=_obligation,
    incomplete_basis="the bounded worker did not establish a conclusion",
    tags=("number-theory", "modular", "discrete-logarithm", "bounded", "sympy"),
    invocation_examples=(
        example(
            "two_to_one_mod_three",
            "Solve 2^x = 1 modulo 3.",
            {
                "base": 2,
                "target": 1,
                "modulus": 3,
                "resource_budget": {"wall_seconds": 1},
            },
        ),
    ),
)
