"""Bounded Python-FLINT rational-solution producer capability."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from jacobian.bounded_process import BoundedProcessResult, run_bounded_process
from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.capabilities import CapabilityAdapter, CapabilityInvocationError
from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityCompleteness,
    CapabilityCompletenessStatus,
    CapabilityDescriptor,
    CapabilityDiagnostic,
    CapabilityMode,
    CapabilityProviderAvailability,
    CapabilityProviderRuntime,
    CapabilityRelationship,
    CapabilityRequest,
    CapabilityResult,
    CapabilityScope,
)
from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.linear import (
    LinearRationalSolutionFindOutput,
    LinearRationalSolutionFindRequest,
)
from jacobian.contracts.results import Execution, ExecutionStatus
from jacobian.flint_linear_worker import FLINT_LINEAR_WORKER_PROTOCOL
from jacobian.linear import LinearArtifactService
from jacobian.provider_runtime import (
    PYTHON_FLINT_VERSION,
    python_flint_provider_runtime,
)
from jacobian.schema_registry import model_schema

FLINT_LINEAR_STDOUT_LIMIT = 64_000
FLINT_LINEAR_STDERR_LIMIT = 64_000


@dataclass(frozen=True, slots=True)
class _FlintLinearRun:
    execution_status: ExecutionStatus
    runtime_ms: int
    values: tuple[CanonicalRational, ...] | None = None
    detail: str | None = None


def install_python_flint_linear_capability(
    linear: LinearArtifactService,
    runtime: CapabilityProviderRuntime,
) -> CapabilityAdapter:
    """Install one producer only for the exact supported optional runtime."""

    if (
        runtime.availability is not CapabilityProviderAvailability.AVAILABLE
        or runtime.provider != "python-flint"
        or runtime.version != PYTHON_FLINT_VERSION
    ):
        raise ValueError("the pinned Python-FLINT runtime is not available")
    return PythonFlintRationalSolutionFindAdapter(linear=linear, runtime=runtime)


class _PythonFlintBackend:
    def __init__(self, runtime: CapabilityProviderRuntime) -> None:
        self.runtime = runtime

    def run(self, request: LinearRationalSolutionFindRequest) -> _FlintLinearRun:
        started = time.monotonic()
        if python_flint_provider_runtime(refresh=True) != self.runtime:
            return _failure(
                started,
                ExecutionStatus.ERROR,
                (
                    "The installed Python-FLINT runtime no longer matches the "
                    "capability descriptor; no solution evidence was retained."
                ),
            )
        command = [
            sys.executable,
            "-I",
            "-m",
            "jacobian.flint_linear_worker",
        ]
        worker_request = {
            "protocol": FLINT_LINEAR_WORKER_PROTOCOL,
            "system": request.system.model_dump(mode="json"),
        }
        try:
            completed = run_bounded_process(
                command,
                input_bytes=canonicalize_json(worker_request),
                timeout_seconds=float(request.resource_budget.wall_seconds),
                environment={
                    "LANG": "C",
                    "LC_ALL": "C",
                    "TZ": "UTC",
                    "PYTHONHASHSEED": "0",
                },
                stdout_limit=FLINT_LINEAR_STDOUT_LIMIT,
                stderr_limit=FLINT_LINEAR_STDERR_LIMIT,
            )
        except OSError:
            return _failure(
                started,
                ExecutionStatus.ERROR,
                "The isolated Python-FLINT worker could not be started.",
            )
        operational = _operational_failure(started, completed)
        if operational is not None:
            return operational
        try:
            values = _parse_worker_output(completed.stdout)
        except (UnicodeDecodeError, ValueError, ValidationError):
            return _failure(
                started,
                ExecutionStatus.ERROR,
                (
                    "The Python-FLINT worker returned output outside its exact "
                    "bounded protocol; no solution evidence was retained."
                ),
            )
        if python_flint_provider_runtime(refresh=True) != self.runtime:
            return _failure(
                started,
                ExecutionStatus.ERROR,
                (
                    "The installed Python-FLINT runtime changed during execution; "
                    "no solution evidence was retained."
                ),
            )
        return _FlintLinearRun(
            execution_status=ExecutionStatus.COMPLETED,
            runtime_ms=_runtime_ms(started),
            values=values,
        )


class PythonFlintRationalSolutionFindAdapter:
    """Produce one exact vector candidate without verifying it."""

    def __init__(
        self,
        *,
        linear: LinearArtifactService,
        runtime: CapabilityProviderRuntime,
    ) -> None:
        self.linear = linear
        self.backend = _PythonFlintBackend(runtime)
        self._descriptor = CapabilityDescriptor(
            capability_id="linear.rational_solution.find",
            version="1",
            title="Find one exact rational solution",
            description=(
                "Use pinned Python-FLINT to return one exact vector for a declared "
                "finite A x = b system over QQ. A not-found outcome makes no "
                "consistency conclusion; verify any returned vector separately."
            ),
            provider="python-flint",
            provider_runtime=runtime,
            modes=(CapabilityMode.EXPLORE,),
            input_schema=model_schema(LinearRationalSolutionFindRequest),
            output_schema=model_schema(LinearRationalSolutionFindOutput),
            tags=(
                "linear-algebra",
                "rational",
                "exact",
                "solution",
                "witness",
                "python-flint",
            ),
        )

    @property
    def descriptor(self) -> CapabilityDescriptor:
        return self._descriptor

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        try:
            validated = LinearRationalSolutionFindRequest.model_validate(request.input)
            system_uri = self.linear.put_system(validated.system).artifact_uri
            resolved = self.linear.resolve_system(system_uri)
        except (ValidationError, ValueError) as exc:
            raise CapabilityInvocationError(
                CapabilityDiagnostic(
                    code="INVALID_RATIONAL_LINEAR_SYSTEM",
                    stage="input_validation",
                    message=str(exc),
                    path="system",
                    schema_uri=self.linear.installation.system_schema_uri,
                    expected=(
                        "one 1..32 by 1..32 exact rational A x = b system with "
                        "unique ordered variable names and canonical reduced entries"
                    ),
                    hint=(
                        'Encode each rational as {"num":"integer","den":"positive '
                        'integer"} and keep coefficient, variable, and RHS dimensions '
                        "aligned."
                    ),
                )
            ) from exc
        run = self.backend.run(validated)
        solution_uri: str | None = None
        if run.execution_status is ExecutionStatus.COMPLETED and run.values is not None:
            solution_uri = self.linear.put_solution(
                system_uri=system_uri,
                values=run.values,
                producer=self.backend.runtime,
                resource_budget=validated.resource_budget,
            ).artifact_uri
        output = LinearRationalSolutionFindOutput(
            status=(
                "SOLUTION_PRODUCED"
                if solution_uri is not None
                else "NO_SOLUTION_PRODUCED"
            ),
            system_uri=system_uri,
            solution_uri=solution_uri,
            solution=run.values if solution_uri is not None else None,
            certificate_available=solution_uri is not None,
            detail=(
                "Python-FLINT produced one exact vector with all free variables "
                "set to zero; the relation remains unverified until independent "
                "replay."
                if solution_uri is not None
                else (
                    run.detail
                    or "No solution witness was produced; no consistency conclusion "
                    "follows."
                )
            ),
        )
        artifact_uris = (
            (system_uri, solution_uri) if solution_uri is not None else (system_uri,)
        )
        relationships = (
            (
                CapabilityRelationship(
                    relation_id="linear.relation.satisfies",
                    source_artifact_uris=(solution_uri,),
                    target_artifact_uris=(system_uri,),
                ),
            )
            if solution_uri is not None
            else ()
        )
        return CapabilityResult(
            capability_id=self.descriptor.capability_id,
            capability_version=self.descriptor.version,
            mode=request.mode,
            execution=Execution(
                status=run.execution_status,
                runtime_ms=run.runtime_ms,
                detail=run.detail,
            ),
            output=output.model_dump(mode="json"),
            scope=CapabilityScope(
                description="the full declared exact rational A x = b system",
                parameters={
                    "declared_scope": "FULL_SYSTEM",
                    "row_count": resolved.binding.row_count,
                    "column_count": resolved.binding.column_count,
                    "variable_order_digest": resolved.binding.variable_order_digest,
                    "free_variable_policy": "ZERO",
                    "wall_seconds": validated.resource_budget.wall_seconds,
                },
                artifact_uri=system_uri,
            ),
            completeness=CapabilityCompleteness(
                status=(
                    CapabilityCompletenessStatus.NOT_APPLICABLE
                    if solution_uri is not None
                    else CapabilityCompletenessStatus.UNKNOWN
                ),
                basis=(
                    "one directly checkable witness was requested and produced; no "
                    "enumeration or uniqueness claim is made"
                    if solution_uri is not None
                    else "the attempt produced no witness; no consistency or "
                    "inconsistency conclusion follows"
                ),
                assurance_level=(
                    CapabilityAssuranceLevel.COMPUTED
                    if run.execution_status is ExecutionStatus.COMPLETED
                    else CapabilityAssuranceLevel.HEURISTIC
                ),
            ),
            assurance=CapabilityAssurance(
                level=(
                    CapabilityAssuranceLevel.COMPUTED
                    if run.execution_status is ExecutionStatus.COMPLETED
                    else CapabilityAssuranceLevel.HEURISTIC
                ),
                basis=(
                    "the pinned exact-arithmetic provider produced a bound vector, "
                    "but provider success does not verify A x = b"
                    if solution_uri is not None
                    else (
                        "the bounded provider attempt completed without witness "
                        "evidence; no opposite conclusion follows"
                        if run.execution_status is ExecutionStatus.COMPLETED
                        else "provider execution did not complete; no mathematical "
                        "conclusion follows"
                    )
                ),
            ),
            artifact_uris=artifact_uris,
            relationships=relationships,
        )


def _parse_worker_output(
    stdout: bytes,
) -> tuple[CanonicalRational, ...] | None:
    if not stdout.endswith(b"\n") or stdout.count(b"\n") != 1:
        raise ValueError("worker output is not exactly one line")
    payload: Any = loads_strict_json(stdout[:-1])
    if (
        not isinstance(payload, dict)
        or payload.get("protocol") != FLINT_LINEAR_WORKER_PROTOCOL
    ):
        raise ValueError("worker protocol mismatch")
    status = payload.get("status")
    if payload.get("backend_version") != PYTHON_FLINT_VERSION:
        raise ValueError("worker backend version mismatch")
    if status == "NO_SOLUTION_PRODUCED":
        if set(payload) != {"protocol", "status", "backend_version"}:
            raise ValueError("not-found output carries unexpected fields")
        return None
    if status != "SOLUTION_PRODUCED" or set(payload) != {
        "protocol",
        "status",
        "backend_version",
        "values",
    }:
        raise ValueError("worker status is invalid")
    values = payload["values"]
    if not isinstance(values, list) or not 1 <= len(values) <= 32:
        raise ValueError("worker solution shape is invalid")
    return tuple(CanonicalRational.model_validate(value) for value in values)


def _operational_failure(
    started: float,
    completed: BoundedProcessResult,
) -> _FlintLinearRun | None:
    if completed.timed_out:
        return _failure(
            started,
            ExecutionStatus.TIMEOUT,
            "The bounded Python-FLINT attempt timed out; no conclusion follows.",
        )
    if completed.stdout_exceeded or completed.stderr_exceeded:
        return _failure(
            started,
            ExecutionStatus.ERROR,
            "The Python-FLINT worker exceeded its output limit.",
        )
    if completed.returncode != 0 or completed.stderr or not completed.stdout:
        return _failure(
            started,
            ExecutionStatus.ERROR,
            "The Python-FLINT worker failed; no solution evidence was retained.",
        )
    return None


def _failure(
    started: float,
    status: ExecutionStatus,
    detail: str,
) -> _FlintLinearRun:
    return _FlintLinearRun(
        execution_status=status,
        runtime_ms=_runtime_ms(started),
        detail=detail,
    )


def _runtime_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))
