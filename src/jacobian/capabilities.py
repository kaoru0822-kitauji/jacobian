"""Extensible model-facing capability registry and invocation service."""

from __future__ import annotations

import importlib
import logging
import re
import time
from typing import TYPE_CHECKING, Protocol, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityCatalog,
    CapabilityDescriptor,
    CapabilityDiagnostic,
    CapabilityRequest,
    CapabilityResult,
)
from jacobian.contracts.memory import ResearchEpisode
from jacobian.contracts.results import Execution, ExecutionStatus
from jacobian.contracts.verification import VerificationRecord
from jacobian.memory import ResearchMemory
from jacobian.store import ArtifactStore, StoreError

if TYPE_CHECKING:
    from jacobian.kernel import JacobianKernel

_ENTRYPOINT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$")
_LOGGER = logging.getLogger(__name__)


class CapabilityError(RuntimeError):
    """A capability descriptor, request, or assurance boundary is invalid."""


class CapabilityInvocationError(RuntimeError):
    """An expected adapter failure that is safe to return to a model."""

    def __init__(self, diagnostic: CapabilityDiagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


class CapabilityAdapter(Protocol):
    """Operator-installed adapter; registration requires no MCP changes."""

    @property
    def descriptor(self) -> CapabilityDescriptor: ...

    def invoke(self, request: CapabilityRequest) -> CapabilityResult: ...


class CapabilityService:
    """Validate, dispatch, trust-check, and remember mathematical operations."""

    def __init__(self, store: ArtifactStore, memory: ResearchMemory) -> None:
        self.store = store
        self.memory = memory
        self._adapters: dict[str, CapabilityAdapter] = {}

    def register(self, adapter: CapabilityAdapter) -> None:
        descriptor = adapter.descriptor
        if descriptor.capability_id in self._adapters:
            raise CapabilityError(
                f"duplicate capability ID: {descriptor.capability_id}"
            )
        _validator(descriptor.input_schema)
        _validator(descriptor.output_schema)
        self._adapters[descriptor.capability_id] = adapter

    def catalog(self) -> CapabilityCatalog:
        return CapabilityCatalog(
            capabilities=tuple(
                self._adapters[name].descriptor for name in sorted(self._adapters)
            )
        )

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        started = time.monotonic()
        try:
            adapter = self._adapters[request.capability_id]
        except KeyError:
            result = _resolution_failure(
                request=request,
                capability_version="not-installed",
                diagnostic=CapabilityDiagnostic(
                    code="UNKNOWN_CAPABILITY",
                    stage="capability_resolution",
                    message=(f"Capability {request.capability_id!r} is not installed."),
                    hint=(
                        "Call capability.describe without capability_id to list "
                        "installed capabilities, then retry with one of those IDs."
                    ),
                ),
                context={
                    "available_capability_ids": sorted(self._adapters),
                },
            )
            _log_invocation(result, started)
            return result
        descriptor = adapter.descriptor
        if request.mode not in descriptor.modes:
            result = _resolution_failure(
                request=request,
                capability_version=descriptor.version,
                diagnostic=CapabilityDiagnostic(
                    code="UNSUPPORTED_MODE",
                    stage="capability_resolution",
                    message=(
                        f"Capability {request.capability_id!r} does not support "
                        f"{request.mode.value} mode."
                    ),
                    hint=(
                        "Call capability.describe for this capability, then retry "
                        "with one of its advertised modes."
                    ),
                ),
                context={
                    "available_modes": [mode.value for mode in descriptor.modes],
                },
            )
            _log_invocation(result, started)
            return result
        try:
            normalized_input = _validate_payload(descriptor.input_schema, request.input)
        except CapabilityError as exc:
            path = _error_path(exc)
            result = _failed_result(
                descriptor=descriptor,
                request=request,
                diagnostic=CapabilityDiagnostic(
                    code="INVALID_REQUEST",
                    stage="capability_input_validation",
                    message=(
                        "The capability input does not match its advertised schema"
                        + (f" at {path}." if path else ".")
                    ),
                    path=path,
                    expected="input matching the capability descriptor JSON Schema",
                    actual_type="object",
                    hint="Call capability.describe and follow the advertised input schema.",
                ),
            )
            _log_invocation(result, started)
            return result
        normalized_request = request.model_copy(update={"input": normalized_input})
        try:
            result = CapabilityResult.model_validate(adapter.invoke(normalized_request))
        except CapabilityInvocationError as exc:
            result = _failed_result(
                descriptor=descriptor,
                request=request,
                diagnostic=exc.diagnostic,
            )
        except Exception as exc:
            _LOGGER.warning(
                "capability %s stopped during execution",
                request.capability_id,
                exc_info=exc,
            )
            result = _failed_result(
                descriptor=descriptor,
                request=request,
                diagnostic=CapabilityDiagnostic(
                    code="ADAPTER_EXECUTION_FAILED",
                    stage="adapter_execution",
                    message="The capability stopped before returning a result.",
                    hint=(
                        "Retry once. If it fails again, inspect the local Jacobian "
                        "log for this capability."
                    ),
                ),
            )
        if (
            result.capability_id != descriptor.capability_id
            or result.capability_version != descriptor.version
            or result.mode is not request.mode
        ):
            raise CapabilityError("adapter result identity differs from its request")
        if result.execution.status is ExecutionStatus.COMPLETED:
            normalized_output = _validate_payload(
                descriptor.output_schema, result.output
            )
            result = result.model_copy(update={"output": normalized_output})
        self._validate_verified_result(result)
        if (
            descriptor.records_episode
            and result.execution.status is ExecutionStatus.COMPLETED
        ):
            episode_uri = self.memory.record(
                ResearchEpisode(
                    capability_id=result.capability_id,
                    capability_version=result.capability_version,
                    mode=result.mode,
                    request=normalized_request.input,
                    result=result.output,
                    assurance_level=result.assurance.level,
                    verification_record_uri=(result.assurance.verification_record_uri),
                    artifact_uris=result.artifact_uris,
                    summary=_episode_summary(result),
                    tags=descriptor.tags,
                )
            )
            result = result.model_copy(update={"episode_uri": episode_uri})
        _log_invocation(result, started)
        return result

    def _validate_verified_result(self, result: CapabilityResult) -> None:
        if result.assurance.level is not CapabilityAssuranceLevel.VERIFIED:
            return
        record_uri = result.assurance.verification_record_uri
        assert record_uri is not None
        try:
            record_artifact = self.store.get(record_uri)
            record = VerificationRecord.model_validate(record_artifact.payload)
        except (StoreError, ValueError) as exc:
            raise CapabilityError(
                "verified capability result has no valid local verification record"
            ) from exc
        if record.evidence_uri not in result.artifact_uris:
            raise CapabilityError(
                "verified capability result does not expose its checked evidence"
            )
        missing_parents = set(record_artifact.manifest.parents) - set(
            result.artifact_uris
        )
        if missing_parents:
            raise CapabilityError(
                "verified capability result omits verification-bound artifacts"
            )
        projected_record = result.output.get("verification_record_uri")
        if projected_record is not None and projected_record != record_uri:
            raise CapabilityError(
                "verified capability output projects a different verification record"
            )
        projected_conclusion = result.output.get("conclusion")
        if (
            projected_conclusion is not None
            and projected_conclusion != record.conclusion.value
        ):
            raise CapabilityError(
                "verified capability output differs from the checked conclusion"
            )


def load_capability_adapter(
    entrypoint: str,
    kernel: JacobianKernel,
) -> CapabilityAdapter:
    """Load one operator-approved ``factory(kernel)`` adapter entrypoint."""

    if not _ENTRYPOINT_PATTERN.fullmatch(entrypoint):
        raise CapabilityError("capability adapter entrypoint has an invalid format")
    module_name, attribute_name = entrypoint.split(":", 1)
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, attribute_name)
        adapter = factory(kernel)
        descriptor = adapter.descriptor
        invoke = adapter.invoke
    except (AttributeError, ImportError, TypeError) as exc:
        raise CapabilityError(
            f"cannot load capability adapter entrypoint: {entrypoint}"
        ) from exc
    if not isinstance(descriptor, CapabilityDescriptor) or not callable(invoke):
        raise CapabilityError("capability adapter does not implement the protocol")
    return cast(CapabilityAdapter, adapter)


def _validator(schema: dict[str, object]) -> Draft202012Validator:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise CapabilityError("capability JSON Schema is invalid") from exc
    return Draft202012Validator(schema)


def _validate_payload(
    schema: dict[str, object],
    payload: dict[str, object],
) -> dict[str, object]:
    normalized = loads_strict_json(canonicalize_json(payload))
    assert isinstance(normalized, dict)
    errors = sorted(
        _validator(schema).iter_errors(normalized),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.absolute_path) or "$"
        raise CapabilityError(f"{location}: {first.message}")
    return normalized


def _episode_summary(result: CapabilityResult) -> str:
    return (
        f"{result.capability_id} {result.mode.value.lower()} "
        f"{result.execution.status.value.lower()} "
        f"({result.assurance.level.value.lower()})"
    )


def _failed_result(
    *,
    descriptor: CapabilityDescriptor,
    request: CapabilityRequest,
    diagnostic: CapabilityDiagnostic,
) -> CapabilityResult:
    return CapabilityResult(
        capability_id=descriptor.capability_id,
        capability_version=descriptor.version,
        mode=request.mode,
        execution=Execution(
            status=ExecutionStatus.ERROR,
            detail=diagnostic.message,
        ),
        output={"error": diagnostic.model_dump(mode="json", exclude_none=True)},
        diagnostics=(diagnostic,),
        assurance=CapabilityAssurance(
            level=CapabilityAssuranceLevel.HEURISTIC,
            basis="execution or input failure; no mathematical conclusion",
        ),
    )


def _resolution_failure(
    *,
    request: CapabilityRequest,
    capability_version: str,
    diagnostic: CapabilityDiagnostic,
    context: dict[str, object],
) -> CapabilityResult:
    return CapabilityResult(
        capability_id=request.capability_id,
        capability_version=capability_version,
        mode=request.mode,
        execution=Execution(
            status=ExecutionStatus.ERROR,
            detail=diagnostic.message,
        ),
        output={
            "error": diagnostic.model_dump(mode="json", exclude_none=True),
            **context,
        },
        diagnostics=(diagnostic,),
        assurance=CapabilityAssurance(
            level=CapabilityAssuranceLevel.HEURISTIC,
            basis="capability resolution failed; no mathematical conclusion",
        ),
    )


def _error_path(exc: Exception) -> str | None:
    path, separator, _ = str(exc).partition(": ")
    return path if separator else None


def _log_invocation(result: CapabilityResult, started: float) -> None:
    elapsed_ms = round((time.monotonic() - started) * 1000)
    diagnostic_codes = (
        ",".join(diagnostic.code for diagnostic in result.diagnostics) or "-"
    )
    _LOGGER.info(
        (
            "capability invocation capability_id=%s version=%s mode=%s "
            "status=%s assurance=%s elapsed_ms=%d diagnostics=%s episode=%s"
        ),
        result.capability_id,
        result.capability_version,
        result.mode.value,
        result.execution.status.value,
        result.assurance.level.value,
        elapsed_ms,
        diagnostic_codes,
        result.episode_uri or "-",
        extra={
            "jacobian_capability_id": result.capability_id,
            "jacobian_capability_version": result.capability_version,
            "jacobian_mode": result.mode.value,
            "jacobian_execution_status": result.execution.status.value,
            "jacobian_assurance_level": result.assurance.level.value,
            "jacobian_elapsed_ms": elapsed_ms,
            "jacobian_diagnostic_codes": tuple(
                diagnostic.code for diagnostic in result.diagnostics
            ),
            "jacobian_episode_uri": result.episode_uri,
        },
    )
