"""Budgeted declarations for complete factorization-derived operations."""

from __future__ import annotations

import signal
import sys

from pydantic import ValidationError

from jacobian.bounded_process import ProcessResourceLimits, run_bounded_process
from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.contracts.capabilities import (
    CapabilityDiagnostic,
    CapabilityInvocationExample,
)
from jacobian.contracts.number_theory import (
    ArithmeticFunctionRequest,
    BooleanResult,
    DivisorListResult,
    FactorizationRequest,
    IntegerValueResult,
    PrimeFactorizationResult,
)
from jacobian.contracts.results import ContractModel, ExecutionStatus
from jacobian.domains._examples import example
from jacobian.operations import (
    ComputedNotApplicable,
    ComputedOperation,
    ComputedOutcome,
    ComputedSuccess,
    OperationExecutionFailure,
)

_PROTOCOL = "jacobian.number-theory.factorization.sympy.v1"
_STDOUT_LIMIT = 2_000_000
_STDERR_LIMIT = 64_000
_ADDRESS_SPACE_LIMIT = 512 * 1024 * 1024


def _diagnostic(code: str, message: str) -> CapabilityDiagnostic:
    return CapabilityDiagnostic(
        code=code,
        stage="integer_factorization",
        message=message,
        hint="Reduce the integer size or increase the bounded wall time.",
    )


def _compute[ResultT: ContractModel](
    operation: str,
    result_model: type[ResultT],
    request: FactorizationRequest | ArithmeticFunctionRequest,
) -> ComputedOutcome[ResultT]:
    if isinstance(request, FactorizationRequest) and int(request.value) == 0:
        return ComputedNotApplicable(
            _diagnostic(
                "INTEGER_FACTORIZATION_NOT_APPLICABLE",
                "Zero has no finite factorization or divisor enumeration.",
            )
        )
    wall_seconds = int(request.resource_budget.wall_seconds)
    try:
        completed = run_bounded_process(
            [
                sys.executable,
                "-I",
                "-m",
                "jacobian.domains.number_theory.factorization_worker",
            ],
            input_bytes=canonicalize_json(
                {
                    "operation": operation,
                    "protocol": _PROTOCOL,
                    "request": request.model_dump(
                        mode="json",
                        exclude={"resource_budget"},
                    ),
                }
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
            resource_limits=ProcessResourceLimits(
                cpu_seconds=wall_seconds + 1,
                address_space_bytes=_ADDRESS_SPACE_LIMIT,
            ),
        )
    except OSError:
        return OperationExecutionFailure(
            status=ExecutionStatus.ERROR,
            diagnostic=_diagnostic(
                "INTEGER_FACTORIZATION_WORKER_START_FAILED",
                "The isolated SymPy worker could not be started safely.",
            ),
        )
    if completed.timed_out:
        return OperationExecutionFailure(
            status=ExecutionStatus.TIMEOUT,
            diagnostic=_diagnostic(
                "INTEGER_FACTORIZATION_TIMEOUT",
                "The factorization budget expired; no complete result is available.",
            ),
        )
    if completed.stdout_exceeded or completed.stderr_exceeded:
        return OperationExecutionFailure(
            status=ExecutionStatus.ERROR,
            diagnostic=_diagnostic(
                "INTEGER_FACTORIZATION_OUTPUT_LIMIT_EXCEEDED",
                "The worker exceeded its bounded output protocol.",
            ),
        )
    resource_signals = {-signal.SIGKILL}
    if (cpu_signal := getattr(signal, "SIGXCPU", None)) is not None:
        resource_signals.add(-cpu_signal)
    if completed.returncode in resource_signals:
        return OperationExecutionFailure(
            status=ExecutionStatus.TIMEOUT,
            diagnostic=_diagnostic(
                "INTEGER_FACTORIZATION_RESOURCE_LIMIT_EXCEEDED",
                "The worker exhausted its CPU or process resource budget; no complete result is available.",
            ),
        )
    if completed.returncode != 0:
        return OperationExecutionFailure(
            status=ExecutionStatus.ERROR,
            diagnostic=_diagnostic(
                "INTEGER_FACTORIZATION_WORKER_FAILED",
                "The isolated SymPy computation failed without a conclusion.",
            ),
        )
    try:
        payload = loads_strict_json(completed.stdout)
        if not isinstance(payload, dict) or set(payload) != {"protocol", "result"}:
            raise ValueError("unexpected worker response fields")
        if payload["protocol"] != _PROTOCOL:
            raise ValueError("worker protocol does not match")
        return ComputedSuccess(result_model.model_validate(payload["result"]))
    except (TypeError, ValueError, ValidationError):
        return OperationExecutionFailure(
            status=ExecutionStatus.ERROR,
            diagnostic=_diagnostic(
                "INTEGER_FACTORIZATION_PROTOCOL_INVALID",
                "The worker returned data outside the exact result contract.",
            ),
        )


def _operation[RequestT: ContractModel, ResultT: ContractModel](
    *,
    capability_id: str,
    title: str,
    description: str,
    operation: str,
    request_model: type[RequestT],
    result_model: type[ResultT],
    tags: tuple[str, ...],
    invocation_examples: tuple[CapabilityInvocationExample, ...] = (),
) -> ComputedOperation[RequestT, ResultT]:
    def implementation(request: RequestT) -> ComputedOutcome[ResultT]:
        if not isinstance(request, (FactorizationRequest, ArithmeticFunctionRequest)):
            raise TypeError("unsupported factorization request model")
        return _compute(operation, result_model, request)

    return ComputedOperation(
        capability_id=capability_id,
        title=title,
        description=description,
        request_model=request_model,
        result_model=result_model,
        implementation=implementation,
        relation_id=capability_id.replace(".compute.", ".relation.", 1),
        tags=tags,
        invocation_examples=invocation_examples,
    )


FACTORIZATION_CAPABILITIES = (
    _operation(
        capability_id="integer.compute.divisors",
        title="Enumerate positive divisors",
        description=(
            "Enumerate every positive divisor in an isolated, resource-bounded "
            "SymPy worker. Timeout is a non-conclusion."
        ),
        operation="divisors",
        request_model=FactorizationRequest,
        result_model=DivisorListResult,
        tags=("number-theory", "enumeration"),
    ),
    _operation(
        capability_id="integer.compute.proper_divisors",
        title="Enumerate proper divisors",
        description=(
            "Enumerate every positive proper divisor in an isolated, "
            "resource-bounded SymPy worker. Timeout is a non-conclusion."
        ),
        operation="proper_divisors",
        request_model=FactorizationRequest,
        result_model=DivisorListResult,
        tags=("number-theory", "enumeration"),
        invocation_examples=(example("proper_divisors_12", "Enumerate the proper divisors of 12.", {"value": "12"}),),
    ),
    _operation(
        capability_id="integer.compute.prime_factorization",
        title="Factor an integer",
        description=(
            "Compute a complete prime-power factorization in an isolated, "
            "resource-bounded SymPy worker. Timeout is a non-conclusion."
        ),
        operation="prime_factorization",
        request_model=FactorizationRequest,
        result_model=PrimeFactorizationResult,
        tags=("number-theory", "factorization"),
    ),
    _operation(
        capability_id="integer.decide.squarefree",
        title="Decide squarefreeness",
        description=(
            "Decide whether a bounded nonnegative integer is square-free in an "
            "isolated, resource-bounded SymPy worker."
        ),
        operation="squarefree",
        request_model=ArithmeticFunctionRequest,
        result_model=BooleanResult,
        tags=("number-theory", "predicate"),
    ),
    _operation(
        capability_id="integer.compute.radical",
        title="Compute integer radical",
        description=(
            "Compute the product of distinct prime divisors in an isolated, "
            "resource-bounded SymPy worker."
        ),
        operation="radical",
        request_model=ArithmeticFunctionRequest,
        result_model=IntegerValueResult,
        tags=("number-theory", "arithmetic-function"),
    ),
)
