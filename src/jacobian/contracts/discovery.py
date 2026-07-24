"""Wire contracts for bounded candidate enumeration experiments."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import Field, StrictInt, model_validator

from jacobian.canonical import canonicalize_json
from jacobian.contracts.common import ArtifactUri, ExperimentUri, Sha256Digest
from jacobian.contracts.evaluation import EvaluationProfile
from jacobian.contracts.results import (
    ContractModel,
    Coverage,
    InputValidation,
    ResultEnvelope,
    Verification,
)


class PluginEnumerationPage(ContractModel):
    """One bounded page returned by an untrusted candidate enumerator."""

    response_version: Literal["1"] = "1"
    candidates: tuple[Any, ...]
    next_cursor: dict[str, Any] | None = None
    complete: bool
    scope: dict[str, Any]

    @model_validator(mode="after")
    def require_progress_and_canonical_data(self) -> Self:
        canonicalize_json(list(self.candidates))
        canonicalize_json(self.scope)
        if self.complete and self.next_cursor is not None:
            raise ValueError("a complete page cannot carry next_cursor")
        if not self.complete and self.next_cursor is None:
            raise ValueError("an incomplete page requires next_cursor")
        if self.next_cursor is not None:
            canonicalize_json(self.next_cursor)
        return self


class PluginCanonicalizationResponse(ContractModel):
    """Untrusted canonical object and symmetry metadata from a domain plugin."""

    response_version: Literal["1"] = "1"
    canonical_payload: Any
    mapping: dict[str, str] = Field(default_factory=dict)
    automorphism_group_order: str | None = None
    orbits: tuple[tuple[str, ...], ...] = ()

    @model_validator(mode="after")
    def require_canonical_metadata(self) -> Self:
        canonicalize_json(self.canonical_payload)
        canonicalize_json(self.mapping)
        canonicalize_json([list(orbit) for orbit in self.orbits])
        if self.automorphism_group_order is not None and (
            not self.automorphism_group_order.isdigit()
            or self.automorphism_group_order == "0"
        ):
            raise ValueError("automorphism_group_order must be a positive integer")
        return self


class StructureCanonicalizationResult(ContractModel):
    """Search-safe canonicalization output; it never self-certifies."""

    schema_version: Literal["1"] = "1"
    structure_uri: ArtifactUri
    canonical_uri: ArtifactUri | None = None
    canonical_key: Sha256Digest | None = None
    canonicalizer_digest: Sha256Digest | None = None
    mapping: dict[str, str] = Field(default_factory=dict)
    automorphism_group_order: str | None = None
    orbits: tuple[tuple[str, ...], ...] = ()
    result: ResultEnvelope


class ExperimentState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSE_REQUESTED = "PAUSE_REQUESTED"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


class EnumerationStopReason(StrEnum):
    COMPLETE = "COMPLETE"
    CANDIDATE_LIMIT = "CANDIDATE_LIMIT"
    WALL_TIME_LIMIT = "WALL_TIME_LIMIT"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class EnumerationBudget(ContractModel):
    candidates_max: StrictInt = Field(ge=1, le=10_000_000)
    wall_seconds: StrictInt = Field(ge=1, le=86_400)
    page_size: StrictInt = Field(default=128, ge=1, le=4096)


class SearchEnumerateRequest(ContractModel):
    request_version: Literal["1"] = "1"
    claim_uri: ArtifactUri
    plugin_id: ArtifactUri
    bounds: dict[str, Any]
    quotient_by_isomorphism: bool = False
    profile: EvaluationProfile = EvaluationProfile.EXACT_CANDIDATE
    seed: StrictInt = 0
    budget: EnumerationBudget

    @model_validator(mode="after")
    def require_canonical_bounds(self) -> Self:
        canonicalize_json(self.bounds)
        return self


class ExperimentHandle(ContractModel):
    schema_version: Literal["1"] = "1"
    experiment_uri: ExperimentUri
    state: ExperimentState


class EnumerationAccounting(ContractModel):
    raw_candidates: StrictInt = Field(default=0, ge=0)
    unique_candidates: StrictInt = Field(default=0, ge=0)
    duplicate_candidates: StrictInt = Field(default=0, ge=0)
    evaluated_candidates: StrictInt = Field(default=0, ge=0)
    pages: StrictInt = Field(default=0, ge=0)

    @model_validator(mode="after")
    def counts_are_consistent(self) -> Self:
        if self.unique_candidates + self.duplicate_candidates != self.raw_candidates:
            raise ValueError("unique and duplicate counts must equal raw candidates")
        if self.evaluated_candidates > self.unique_candidates:
            raise ValueError("evaluated candidates cannot exceed unique candidates")
        return self


class ExperimentSnapshot(ContractModel):
    schema_version: Literal["1"] = "1"
    experiment_uri: ExperimentUri
    kind: Literal["ENUMERATION"] = "ENUMERATION"
    state: ExperimentState
    request: SearchEnumerateRequest
    input: InputValidation
    created_at: datetime
    updated_at: datetime
    stop_reason: EnumerationStopReason | None = None
    enumerator_reported_complete: bool = False
    coverage: Coverage = Coverage.BOUNDED
    verification: Verification = Verification.UNVERIFIED
    scope_uri: ArtifactUri | None = None
    archive_uri: ArtifactUri | None = None
    archive_page_uris: tuple[ArtifactUri, ...] = ()
    enumerator_digest: Sha256Digest | None = None
    canonicalizer_digest: Sha256Digest | None = None
    evaluator_digest: Sha256Digest | None = None
    accounting: EnumerationAccounting = Field(default_factory=EnumerationAccounting)
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
            raise ValueError("a nonterminal experiment cannot have a stop reason")
        expected_terminal_reasons = {
            ExperimentState.COMPLETED: {
                EnumerationStopReason.COMPLETE,
                EnumerationStopReason.CANDIDATE_LIMIT,
            },
            ExperimentState.CANCELLED: {EnumerationStopReason.CANCELLED},
            ExperimentState.TIMEOUT: {EnumerationStopReason.WALL_TIME_LIMIT},
            ExperimentState.ERROR: {EnumerationStopReason.ERROR},
        }
        if terminal and self.stop_reason not in expected_terminal_reasons[self.state]:
            raise ValueError("terminal experiment state and stop reason disagree")
        if self.coverage == Coverage.EXHAUSTIVE and (
            self.state != ExperimentState.COMPLETED
            or self.stop_reason != EnumerationStopReason.COMPLETE
            or not self.enumerator_reported_complete
        ):
            raise ValueError(
                "exhaustive coverage requires a complete enumerator report"
            )
        if self.verification != Verification.UNVERIFIED:
            raise ValueError("search experiments cannot self-certify")
        return self


class EnumerationArchive(ContractModel):
    schema_version: Literal["1"] = "1"
    experiment_uri: ExperimentUri
    page_index: StrictInt = Field(ge=0)
    candidate_uris: tuple[ArtifactUri, ...]
    evaluation_uris: tuple[ArtifactUri, ...]
    canonical_keys: tuple[Sha256Digest, ...]

    @model_validator(mode="after")
    def aligned_archive_rows(self) -> Self:
        if not (
            len(self.candidate_uris)
            == len(self.evaluation_uris)
            == len(self.canonical_keys)
        ):
            raise ValueError("archive columns must have equal lengths")
        return self


class EnumerationArchiveManifest(ContractModel):
    schema_version: Literal["1"] = "1"
    experiment_uri: ExperimentUri
    page_uris: tuple[ArtifactUri, ...]
    accounting: EnumerationAccounting


class ExperimentCancelResult(ContractModel):
    schema_version: Literal["1"] = "1"
    experiment_uri: ExperimentUri
    state: ExperimentState
    accepted: bool
    detail: str = ""
