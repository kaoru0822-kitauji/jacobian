"""Strategy-neutral contracts for durable search orchestration."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import Field, StrictInt, StringConstraints, model_validator

from jacobian.canonical import canonicalize_json
from jacobian.contracts.common import (
    ArtifactUri,
    CheckerUri,
    ExperimentUri,
    Sha256Digest,
)
from jacobian.contracts.discovery import ExperimentState
from jacobian.contracts.evaluation import EvaluationProfile
from jacobian.contracts.evidence import WitnessRole
from jacobian.contracts.results import (
    ContractModel,
    InputValidation,
    Verification,
)

IdempotencyKey = Annotated[
    str,
    StringConstraints(
        pattern=r"^[A-Za-z0-9._:-]{8,128}$",
        strict=True,
    ),
]


class SearchStopReason(StrEnum):
    STRATEGY_COMPLETE = "STRATEGY_COMPLETE"
    CANDIDATE_LIMIT = "CANDIDATE_LIMIT"
    ITERATION_LIMIT = "ITERATION_LIMIT"
    WALL_TIME_LIMIT = "WALL_TIME_LIMIT"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class SearchBudget(ContractModel):
    """Hard strategy limits; the provisional scheduler supports one worker."""

    candidates_max: StrictInt = Field(ge=1, le=10_000_000)
    iterations_max: StrictInt = Field(ge=1, le=10_000_000)
    wall_seconds: StrictInt = Field(ge=1, le=86_400)
    batch_size: StrictInt = Field(default=32, ge=1, le=4096)
    workers: StrictInt = Field(default=1, ge=1, le=1)


class SearchRunRequest(ContractModel):
    """One canonical request bound durably by its idempotency key."""

    request_version: Literal["1"] = "1"
    idempotency_key: IdempotencyKey
    claim_uri: ArtifactUri
    plugin_id: ArtifactUri
    initial_state: dict[str, Any] = Field(default_factory=dict)
    profile: EvaluationProfile = EvaluationProfile.EXACT_CANDIDATE
    seed: StrictInt = 0
    witness_role: WitnessRole | None = None
    counterexample_checker_id: CheckerUri | None = None
    budget: SearchBudget

    @model_validator(mode="after")
    def validate_search_policy(self) -> Self:
        canonicalize_json(self.initial_state)
        if (self.witness_role is None) != (self.counterexample_checker_id is None):
            raise ValueError(
                "Set both witness_role and counterexample_checker_id, or omit both. "
                "Use the reference contract to choose the checker."
            )
        if self.witness_role is not None and self.witness_role not in {
            WitnessRole.DEFEATS_CANDIDATE,
            WitnessRole.REFUTES_CLAIM,
        }:
            raise ValueError(
                "Search counterexample feedback requires witness_role "
                "DEFEATS_CANDIDATE or REFUTES_CLAIM."
            )
        return self


class PluginProposalResponse(ContractModel):
    response_version: Literal["1"] = "1"
    candidates: tuple[dict[str, Any], ...] = ()
    state: dict[str, Any] = Field(default_factory=dict)
    complete: bool = False
    detail: str = ""

    @model_validator(mode="after")
    def require_progress(self) -> Self:
        canonicalize_json(self.state)
        for candidate in self.candidates:
            canonicalize_json(candidate)
        if not self.candidates and not self.complete:
            raise ValueError("proposer must return candidates or report completion")
        return self


class SearchCandidateRecord(ContractModel):
    candidate_uri: ArtifactUri
    evaluation_uri: ArtifactUri
    witness_uri: ArtifactUri | None = None
    verification_record_uri: ArtifactUri | None = None
    counterexample_verified: bool = False
    detail: str = ""

    @model_validator(mode="after")
    def bind_verified_counterexample(self) -> Self:
        if self.counterexample_verified and (
            self.witness_uri is None or self.verification_record_uri is None
        ):
            raise ValueError(
                "verified counterexample requires witness and verification record"
            )
        if (
            self.verification_record_uri is not None
            and not self.counterexample_verified
        ):
            raise ValueError(
                "counterexample verification record requires verified status"
            )
        return self


class SearchNomination(ContractModel):
    candidate_uri: ArtifactUri
    reason: str = Field(min_length=1, max_length=512)


class PluginRefinementResponse(ContractModel):
    response_version: Literal["1"] = "1"
    state: dict[str, Any] = Field(default_factory=dict)
    nominations: tuple[SearchNomination, ...] = ()
    detail: str = ""

    @model_validator(mode="after")
    def require_canonical_state(self) -> Self:
        canonicalize_json(self.state)
        return self


class SearchAccounting(ContractModel):
    """Committed operation counts and measured checkpoint-boundary wall time."""

    proposed_candidates: StrictInt = Field(default=0, ge=0)
    unique_candidates: StrictInt = Field(default=0, ge=0)
    duplicate_candidates: StrictInt = Field(default=0, ge=0)
    evaluated_candidates: StrictInt = Field(default=0, ge=0)
    attacked_candidates: StrictInt = Field(default=0, ge=0)
    verified_counterexamples: StrictInt = Field(default=0, ge=0)
    iterations: StrictInt = Field(default=0, ge=0)
    checkpoints: StrictInt = Field(default=0, ge=0)
    nominations: StrictInt = Field(default=0, ge=0)
    wall_time_ms: StrictInt = Field(default=0, ge=0)

    @model_validator(mode="after")
    def counts_are_consistent(self) -> Self:
        if (
            self.unique_candidates + self.duplicate_candidates
            != self.proposed_candidates
        ):
            raise ValueError(
                "unique and duplicate counts must equal proposed candidates"
            )
        if self.evaluated_candidates > self.unique_candidates:
            raise ValueError("evaluated candidates cannot exceed unique candidates")
        if self.attacked_candidates > self.evaluated_candidates:
            raise ValueError("attacked candidates cannot exceed evaluated candidates")
        if self.verified_counterexamples > self.attacked_candidates:
            raise ValueError(
                "verified counterexamples cannot exceed attacked candidates"
            )
        if self.checkpoints > self.iterations:
            raise ValueError("checkpoints cannot exceed completed iterations")
        if self.nominations > self.unique_candidates:
            raise ValueError("nominations cannot exceed unique candidates")
        return self


class SearchCheckpoint(ContractModel):
    """Immutable opaque strategy state rebound to all execution identities."""

    schema_version: Literal["1"] = "1"
    experiment_uri: ExperimentUri
    request_digest: Sha256Digest
    iteration: StrictInt = Field(ge=0)
    state: dict[str, Any] = Field(default_factory=dict)
    latest_records: tuple[SearchCandidateRecord, ...] = ()
    nominations: tuple[SearchNomination, ...] = ()
    accounting: SearchAccounting = Field(default_factory=SearchAccounting)
    effective_budget: SearchBudget
    registry_snapshot_uri: ArtifactUri
    proposer_digest: Sha256Digest
    refiner_digest: Sha256Digest
    evaluator_digest: Sha256Digest
    environment_digest: Sha256Digest
    previous_checkpoint_uri: ArtifactUri | None = None

    @model_validator(mode="after")
    def require_canonical_state(self) -> Self:
        canonicalize_json(self.state)
        return self


class SearchArchivePage(ContractModel):
    schema_version: Literal["1"] = "1"
    experiment_uri: ExperimentUri
    request_digest: Sha256Digest
    claim_uri: ArtifactUri
    plugin_id: ArtifactUri
    registry_snapshot_uri: ArtifactUri
    iteration: StrictInt = Field(ge=1)
    proposer_digest: Sha256Digest
    refiner_digest: Sha256Digest
    evaluator_digest: Sha256Digest
    records: tuple[SearchCandidateRecord, ...]
    nominations: tuple[SearchNomination, ...] = ()


class SearchArchiveManifest(ContractModel):
    schema_version: Literal["1"] = "1"
    experiment_uri: ExperimentUri
    request_digest: Sha256Digest
    claim_uri: ArtifactUri
    plugin_id: ArtifactUri
    registry_snapshot_uri: ArtifactUri
    page_uris: tuple[ArtifactUri, ...]
    accounting: SearchAccounting
    effective_budget: SearchBudget
    environment_digest: Sha256Digest


class SearchExperimentSnapshot(ContractModel):
    """Mutable lifecycle index whose mathematical assurance stays unverified."""

    schema_version: Literal["1"] = "1"
    experiment_uri: ExperimentUri
    kind: Literal["SEARCH"] = "SEARCH"
    state: ExperimentState
    request: SearchRunRequest
    input: InputValidation
    created_at: datetime
    updated_at: datetime
    stop_reason: SearchStopReason | None = None
    strategy_reported_complete: bool = False
    verification: Verification = Verification.UNVERIFIED
    checkpoint_uri: ArtifactUri | None = None
    archive_uri: ArtifactUri | None = None
    archive_page_uris: tuple[ArtifactUri, ...] = ()
    request_digest: Sha256Digest
    effective_budget: SearchBudget
    registry_snapshot_uri: ArtifactUri
    proposer_digest: Sha256Digest | None = None
    refiner_digest: Sha256Digest | None = None
    evaluator_digest: Sha256Digest | None = None
    environment_digest: Sha256Digest
    accounting: SearchAccounting = Field(default_factory=SearchAccounting)
    detail: str = ""

    @model_validator(mode="after")
    def fail_closed_lifecycle(self) -> Self:
        terminal = self.state in {
            ExperimentState.COMPLETED,
            ExperimentState.CANCELLED,
            ExperimentState.TIMEOUT,
            ExperimentState.ERROR,
        }
        if not terminal and self.stop_reason is not None:
            raise ValueError("a nonterminal search cannot have a stop reason")
        expected_terminal_reasons = {
            ExperimentState.COMPLETED: {
                SearchStopReason.STRATEGY_COMPLETE,
                SearchStopReason.CANDIDATE_LIMIT,
                SearchStopReason.ITERATION_LIMIT,
            },
            ExperimentState.CANCELLED: {SearchStopReason.CANCELLED},
            ExperimentState.TIMEOUT: {SearchStopReason.WALL_TIME_LIMIT},
            ExperimentState.ERROR: {SearchStopReason.ERROR},
        }
        if terminal and self.stop_reason not in expected_terminal_reasons[self.state]:
            raise ValueError("terminal search state and stop reason disagree")
        if (
            self.stop_reason is SearchStopReason.STRATEGY_COMPLETE
            and not self.strategy_reported_complete
        ):
            raise ValueError(
                "strategy-complete stop requires a complete strategy report"
            )
        if self.verification is not Verification.UNVERIFIED:
            raise ValueError("search experiments cannot self-certify")
        return self


class ExperimentControlResult(ContractModel):
    schema_version: Literal["1"] = "1"
    experiment_uri: ExperimentUri
    state: ExperimentState
    accepted: bool
    detail: str = ""


class SearchLifecycleEvent(ContractModel):
    schema_version: Literal["1"] = "1"
    experiment_uri: ExperimentUri
    sequence: StrictInt = Field(ge=0)
    event_type: str = Field(min_length=1, max_length=64)
    occurred_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
    previous_event_digest: Sha256Digest | None = None
    event_digest: Sha256Digest

    @model_validator(mode="after")
    def require_canonical_payload(self) -> Self:
        canonicalize_json(self.payload)
        return self
