"""Bounded contracts for the external model-authored reasoning log."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from jacobian.canonical import canonicalize_json
from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityId,
    CapabilityMode,
)
from jacobian.contracts.results import ContractModel, ExecutionStatus

_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
ReasoningRunId = Annotated[str, StringConstraints(pattern=_UUID_PATTERN, strict=True)]
ReasoningCallId = Annotated[str, StringConstraints(pattern=_UUID_PATTERN, strict=True)]


class ReasoningPhase(StrEnum):
    PLAN = "PLAN"
    BEFORE_TOOL = "BEFORE_TOOL"
    AFTER_TOOL = "AFTER_TOOL"
    FINAL = "FINAL"


class ReasoningInterpretationStatus(StrEnum):
    """Whether the model received enough result content to interpret the call."""

    INTERPRETED = "INTERPRETED"
    RESULT_UNAVAILABLE = "RESULT_UNAVAILABLE"


class ReasoningRunState(StrEnum):
    READY = "READY"
    READY_TO_INVOKE = "READY_TO_INVOKE"
    TOOL_RUNNING = "TOOL_RUNNING"
    AWAITING_AFTER_TOOL = "AWAITING_AFTER_TOOL"
    FINALIZED = "FINALIZED"


class ReasoningNextRequired(StrEnum):
    BEFORE_TOOL_OR_FINAL = "BEFORE_TOOL_OR_FINAL"
    CAPABILITY_INVOKE = "CAPABILITY_INVOKE"
    AFTER_TOOL = "AFTER_TOOL"
    NONE = "NONE"


class ReasoningWriteRequest(ContractModel):
    """One concise model-authored summary; never hidden chain-of-thought."""

    schema_version: Literal["1"] = "1"
    phase: ReasoningPhase
    summary: str = Field(min_length=1, max_length=512)
    run_id: ReasoningRunId | None = None
    call_id: ReasoningCallId | None = None
    capability_id: CapabilityId | None = None
    mode: CapabilityMode | None = None
    interpretation_status: ReasoningInterpretationStatus | None = None
    reported_execution_status: ExecutionStatus | None = None
    reported_assurance_level: CapabilityAssuranceLevel | None = None
    reported_completeness_status: CapabilityCompletenessStatus | None = None

    @model_validator(mode="after")
    def validate_phase_shape_and_size(self) -> Self:
        if not self.summary.strip():
            raise ValueError("summary must contain non-whitespace text")
        if len(self.summary.encode("utf-8")) > 2048:
            raise ValueError("summary must be at most 2048 UTF-8 bytes")
        required: dict[ReasoningPhase, tuple[bool, bool, bool, bool, bool]] = {
            ReasoningPhase.PLAN: (False, False, False, False, False),
            ReasoningPhase.BEFORE_TOOL: (True, False, True, True, False),
            ReasoningPhase.AFTER_TOOL: (True, True, False, False, True),
            ReasoningPhase.FINAL: (True, False, False, False, False),
        }
        actual = (
            self.run_id is not None,
            self.call_id is not None,
            self.capability_id is not None,
            self.mode is not None,
            self.interpretation_status is not None,
        )
        if actual != required[self.phase]:
            raise ValueError(f"fields do not match {self.phase.value} phase contract")
        reported = (
            self.reported_execution_status,
            self.reported_assurance_level,
            self.reported_completeness_status,
        )
        if self.interpretation_status is ReasoningInterpretationStatus.INTERPRETED:
            if any(value is None for value in reported):
                raise ValueError("INTERPRETED requires all reported result fields")
        elif any(value is not None for value in reported):
            raise ValueError("reported result fields require INTERPRETED")
        return self


class ReasoningWriteResult(ContractModel):
    schema_version: Literal["1"] = "1"
    run_id: ReasoningRunId
    call_id: ReasoningCallId | None = None
    sequence: int = Field(ge=0, strict=True)
    state: ReasoningRunState
    next_required: ReasoningNextRequired
    log_uri: str = Field(pattern=r"^reasoning://run/[0-9a-f-]{36}$")
    execution_status_matches: bool | None = None
    assurance_level_matches: bool | None = None
    completeness_status_matches: bool | None = None


class ReasoningEvent(ContractModel):
    """Canonical durable event shared by model and system writers."""

    schema_version: Literal["1"] = "1"
    run_id: ReasoningRunId
    sequence: int = Field(ge=0, strict=True)
    kind: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    occurred_at: str = Field(min_length=20, max_length=64)
    payload: dict[str, Any]

    @model_validator(mode="after")
    def require_canonical_payload(self) -> Self:
        canonicalize_json(self.payload)
        return self


__all__ = [
    "ReasoningCallId",
    "ReasoningEvent",
    "ReasoningInterpretationStatus",
    "ReasoningNextRequired",
    "ReasoningPhase",
    "ReasoningRunId",
    "ReasoningRunState",
    "ReasoningWriteRequest",
    "ReasoningWriteResult",
]
