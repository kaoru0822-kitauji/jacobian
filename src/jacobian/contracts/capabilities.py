"""Model-facing contracts for extensible mathematical capabilities."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from jacobian.canonical import canonicalize_json
from jacobian.contracts.common import ArtifactUri
from jacobian.contracts.results import ContractModel, Execution

CapabilityId = Annotated[
    str,
    StringConstraints(
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$",
        min_length=3,
        max_length=128,
        strict=True,
    ),
]


class CapabilityMode(StrEnum):
    """The low-friction exploration and explicit verification lanes."""

    EXPLORE = "EXPLORE"
    VERIFY = "VERIFY"


class CapabilityAssuranceLevel(StrEnum):
    """Coarse model-facing assurance without hiding the detailed result record."""

    HEURISTIC = "HEURISTIC"
    COMPUTED = "COMPUTED"
    VERIFIED = "VERIFIED"


class CapabilityRelationshipStatus(StrEnum):
    """Whether a returned mathematical relationship has checker backing."""

    PROPOSED = "PROPOSED"
    VERIFIED = "VERIFIED"


class CapabilityObligationStatus(StrEnum):
    """Lifecycle of a proof obligation created by a capability."""

    OPEN = "OPEN"
    DISCHARGED = "DISCHARGED"


class CapabilityCompletenessStatus(StrEnum):
    """How much of the explicitly declared scope an operation covered."""

    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"


class CapabilityDescriptor(ContractModel):
    """One installed operation advertised by an operator-installed adapter."""

    descriptor_version: Literal["1"] = "1"
    capability_id: CapabilityId
    version: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=512)
    provider: str = Field(min_length=1, max_length=128)
    modes: tuple[CapabilityMode, ...]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    read_only: bool = False
    records_episode: bool = True
    tags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_modes_and_canonical_schemas(self) -> Self:
        if not self.modes:
            raise ValueError("a capability must support at least one mode")
        if len(set(self.modes)) != len(self.modes):
            raise ValueError("capability modes must be unique")
        canonicalize_json(self.input_schema)
        canonicalize_json(self.output_schema)
        return self


class CapabilityRequest(ContractModel):
    request_version: Literal["1"] = "1"
    capability_id: CapabilityId
    mode: CapabilityMode = CapabilityMode.EXPLORE
    input: dict[str, Any]

    @model_validator(mode="after")
    def require_canonical_input(self) -> Self:
        canonicalize_json(self.input)
        return self


class CapabilityAssurance(ContractModel):
    level: CapabilityAssuranceLevel
    basis: str = Field(min_length=1, max_length=1024)
    verification_record_uri: ArtifactUri | None = None

    @model_validator(mode="after")
    def bind_verified_assurance(self) -> Self:
        if (
            self.level is CapabilityAssuranceLevel.VERIFIED
            and self.verification_record_uri is None
        ):
            raise ValueError("verified capability assurance requires a record URI")
        if (
            self.level is not CapabilityAssuranceLevel.VERIFIED
            and self.verification_record_uri is not None
        ):
            raise ValueError(
                "only verified capability assurance may carry a record URI"
            )
        return self


class CapabilityScope(ContractModel):
    """Domain-owned scope parameters, optionally materialized as an artifact."""

    description: str | None = Field(default=None, min_length=1, max_length=512)
    parameters: dict[str, Any] = Field(default_factory=dict)
    artifact_uri: ArtifactUri | None = None

    @model_validator(mode="after")
    def require_explicit_scope(self) -> Self:
        canonicalize_json(self.parameters)
        if not self.parameters and self.artifact_uri is None:
            raise ValueError("scope requires parameters or an artifact URI")
        return self


class CapabilityCompleteness(ContractModel):
    """Coverage claim over the result's exact declared scope."""

    status: CapabilityCompletenessStatus = CapabilityCompletenessStatus.NOT_APPLICABLE
    basis: str = Field(min_length=1, max_length=1024)
    assurance_level: CapabilityAssuranceLevel = CapabilityAssuranceLevel.HEURISTIC
    verification_record_uri: ArtifactUri | None = None

    @model_validator(mode="after")
    def bind_verified_completeness(self) -> Self:
        if (
            self.assurance_level is CapabilityAssuranceLevel.VERIFIED
            and self.verification_record_uri is None
        ):
            raise ValueError("verified completeness requires a record URI")
        if (
            self.assurance_level is not CapabilityAssuranceLevel.VERIFIED
            and self.verification_record_uri is not None
        ):
            raise ValueError("only verified completeness may carry a record URI")
        if (
            self.status is not CapabilityCompletenessStatus.COMPLETE
            and self.assurance_level is CapabilityAssuranceLevel.VERIFIED
        ):
            raise ValueError("only complete coverage may be independently verified")
        return self


class CapabilityRelationship(ContractModel):
    """A domain-owned relationship between exact immutable artifacts."""

    relation_id: CapabilityId
    source_artifact_uris: tuple[ArtifactUri, ...]
    target_artifact_uris: tuple[ArtifactUri, ...]
    status: CapabilityRelationshipStatus = CapabilityRelationshipStatus.PROPOSED
    obligation_uris: tuple[ArtifactUri, ...] = ()
    verification_record_uri: ArtifactUri | None = None

    @model_validator(mode="after")
    def require_bound_endpoints(self) -> Self:
        if not self.source_artifact_uris or not self.target_artifact_uris:
            raise ValueError("relationship requires source and target artifacts")
        if len(set(self.source_artifact_uris)) != len(self.source_artifact_uris):
            raise ValueError("relationship source artifacts must be unique")
        if len(set(self.target_artifact_uris)) != len(self.target_artifact_uris):
            raise ValueError("relationship target artifacts must be unique")
        if (
            self.status is CapabilityRelationshipStatus.VERIFIED
            and self.verification_record_uri is None
        ):
            raise ValueError("verified relationship requires a record URI")
        if (
            self.status is CapabilityRelationshipStatus.PROPOSED
            and self.verification_record_uri is not None
        ):
            raise ValueError("proposed relationship cannot carry a record URI")
        return self


class CapabilityObligation(ContractModel):
    """One materialized proof obligation and its checker-backed lifecycle."""

    obligation_uri: ArtifactUri
    status: CapabilityObligationStatus = CapabilityObligationStatus.OPEN
    verification_record_uri: ArtifactUri | None = None

    @model_validator(mode="after")
    def require_record_for_discharge(self) -> Self:
        if (
            self.status is CapabilityObligationStatus.DISCHARGED
            and self.verification_record_uri is None
        ):
            raise ValueError("discharged obligation requires a record URI")
        if (
            self.status is CapabilityObligationStatus.OPEN
            and self.verification_record_uri is not None
        ):
            raise ValueError("open obligation cannot carry a record URI")
        return self


class CapabilityDiagnostic(ContractModel):
    """Actionable, stage-aware failure information without a truth claim."""

    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    stage: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    message: str = Field(min_length=1, max_length=1024)
    path: str | None = Field(default=None, max_length=512)
    schema_uri: ArtifactUri | None = None
    expected: str | None = Field(default=None, max_length=1024)
    actual_type: str | None = Field(default=None, max_length=128)
    hint: str | None = Field(default=None, max_length=1024)


class CapabilityResult(ContractModel):
    """Compact result shared by local, MCP, and remote capability adapters."""

    response_version: Literal["2"] = "2"
    capability_id: CapabilityId
    capability_version: str = Field(min_length=1, max_length=64)
    mode: CapabilityMode
    execution: Execution
    output: dict[str, Any] = Field(default_factory=dict)
    scope: CapabilityScope | None = None
    completeness: CapabilityCompleteness = Field(
        default_factory=lambda: CapabilityCompleteness(
            basis="the operation makes no completeness claim",
        )
    )
    relationships: tuple[CapabilityRelationship, ...] = ()
    obligations: tuple[CapabilityObligation, ...] = ()
    diagnostics: tuple[CapabilityDiagnostic, ...] = ()
    assurance: CapabilityAssurance
    artifact_uris: tuple[ArtifactUri, ...] = ()
    episode_uri: ArtifactUri | None = None

    @model_validator(mode="after")
    def enforce_lane_and_canonical_output(self) -> Self:
        canonicalize_json(self.output)
        if self.execution.status.value == "COMPLETED" and self.diagnostics:
            raise ValueError("completed capability execution cannot carry diagnostics")
        if (
            self.assurance.level is CapabilityAssuranceLevel.VERIFIED
            and self.mode is not CapabilityMode.VERIFY
        ):
            raise ValueError("the exploration lane cannot return verified assurance")
        if (
            self.execution.status.value != "COMPLETED"
            and self.assurance.level is CapabilityAssuranceLevel.VERIFIED
        ):
            raise ValueError("failed capability execution cannot be verified")
        if (
            self.completeness.status is CapabilityCompletenessStatus.COMPLETE
            and self.scope is None
        ):
            raise ValueError("complete result requires explicit scope")
        if (
            self.execution.status.value != "COMPLETED"
            and self.completeness.status is CapabilityCompletenessStatus.COMPLETE
        ):
            raise ValueError("failed execution cannot be complete")
        record_uri = self.assurance.verification_record_uri
        for relationship in self.relationships:
            if relationship.status is CapabilityRelationshipStatus.VERIFIED:
                if self.assurance.level is not CapabilityAssuranceLevel.VERIFIED:
                    raise ValueError(
                        "verified relationship requires verified result assurance"
                    )
                if relationship.verification_record_uri != record_uri:
                    raise ValueError(
                        "verified relationship must use the result verification record"
                    )
        for obligation in self.obligations:
            if obligation.status is CapabilityObligationStatus.DISCHARGED:
                if self.assurance.level is not CapabilityAssuranceLevel.VERIFIED:
                    raise ValueError(
                        "discharged obligation requires verified result assurance"
                    )
                if obligation.verification_record_uri != record_uri:
                    raise ValueError(
                        "discharged obligation must use the result verification record"
                    )
        if self.completeness.assurance_level is CapabilityAssuranceLevel.VERIFIED:
            if self.assurance.level is not CapabilityAssuranceLevel.VERIFIED:
                raise ValueError(
                    "verified completeness requires verified result assurance"
                )
            if self.completeness.verification_record_uri != record_uri:
                raise ValueError(
                    "verified completeness must use the result verification record"
                )
        return self


class CapabilityCatalog(ContractModel):
    catalog_version: Literal["1"] = "1"
    capabilities: tuple[CapabilityDescriptor, ...]
