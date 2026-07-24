"""Contracts for hypothesis-producing conjecture workflows."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import Field, StrictInt, model_validator

from jacobian.canonical import canonicalize_json
from jacobian.contracts.common import (
    ArtifactUri,
    CheckerUri,
    ExperimentUri,
    Sha256Digest,
)
from jacobian.contracts.evidence import WitnessRole
from jacobian.contracts.results import (
    ContractModel,
    Execution,
    InputStatus,
    InputValidation,
    Verification,
)
from jacobian.contracts.search import SearchBudget


class ConjectureOperation(StrEnum):
    REPAIR = "REPAIR"
    GENERATE = "GENERATE"
    PARAMETER_GENERALIZE = "PARAMETER_GENERALIZE"


class NoveltyAssessment(StrEnum):
    UNKNOWN = "UNKNOWN"
    UNIQUE_WITHIN_REQUEST = "UNIQUE_WITHIN_REQUEST"


class ParameterRegionEvidence(StrEnum):
    PROPOSED = "PROPOSED"
    SAMPLED = "SAMPLED"
    VERIFIED_SUFFICIENT = "VERIFIED_SUFFICIENT"
    VERIFIED_NECESSARY = "VERIFIED_NECESSARY"


class HypothesisEdit(ContractModel):
    kind: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=512)
    path: str | None = Field(default=None, max_length=512)
    before: Any = None
    after: Any = None

    @model_validator(mode="after")
    def require_canonical_values(self) -> Self:
        canonicalize_json({"before": self.before, "after": self.after})
        return self


class ParameterRegion(ContractModel):
    conditions: dict[str, Any]
    evidence: ParameterRegionEvidence
    sample_uris: tuple[ArtifactUri, ...] = ()
    verification_record_uri: ArtifactUri | None = None

    @model_validator(mode="after")
    def evidence_boundary(self) -> Self:
        canonicalize_json(self.conditions)
        verified = self.evidence in {
            ParameterRegionEvidence.VERIFIED_SUFFICIENT,
            ParameterRegionEvidence.VERIFIED_NECESSARY,
        }
        if verified and self.verification_record_uri is None:
            raise ValueError("verified parameter regions require a verification record")
        if not verified and self.verification_record_uri is not None:
            raise ValueError(
                "unverified parameter regions cannot cite a verification record"
            )
        if self.evidence is ParameterRegionEvidence.SAMPLED and not self.sample_uris:
            raise ValueError("sampled parameter regions require sample artifacts")
        return self


class PluginHypothesisProposal(ContractModel):
    claim: dict[str, Any]
    edit: HypothesisEdit
    metrics: dict[str, Any] = Field(default_factory=dict)
    parameter_region: ParameterRegion | None = None
    detail: str = ""

    @model_validator(mode="after")
    def plugin_output_remains_unverified(self) -> Self:
        canonicalize_json(self.claim)
        canonicalize_json(self.metrics)
        if self.parameter_region is not None and self.parameter_region.evidence in {
            ParameterRegionEvidence.VERIFIED_SUFFICIENT,
            ParameterRegionEvidence.VERIFIED_NECESSARY,
        }:
            raise ValueError(
                "hypothesis plugins cannot promote parameter-region evidence"
            )
        return self


class PluginHypothesisResponse(ContractModel):
    response_version: Literal["1"] = "1"
    proposals: tuple[PluginHypothesisProposal, ...] = ()
    state: dict[str, Any] = Field(default_factory=dict)
    complete: bool = False
    detail: str = ""

    @model_validator(mode="after")
    def require_progress(self) -> Self:
        canonicalize_json(self.state)
        if not self.proposals and not self.complete:
            raise ValueError(
                "hypothesis transformer must return proposals or report completion"
            )
        return self


class FalsificationPlan(ContractModel):
    initial_state: dict[str, Any] = Field(default_factory=dict)
    witness_role: WitnessRole | None = None
    counterexample_checker_id: CheckerUri | None = None
    budget: SearchBudget

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        canonicalize_json(self.initial_state)
        if (self.witness_role is None) != (self.counterexample_checker_id is None):
            raise ValueError(
                "witness role and counterexample checker must be configured together"
            )
        if self.witness_role is not None and self.witness_role not in {
            WitnessRole.DEFEATS_CANDIDATE,
            WitnessRole.REFUTES_CLAIM,
        }:
            raise ValueError("falsification requires a defeating or refuting witness")
        return self


class ConjectureWorkflowRequest(ContractModel):
    request_version: Literal["1"] = "1"
    operation: ConjectureOperation
    plugin_id: ArtifactUri
    source_uri: ArtifactUri | None = None
    verification_record_uri: ArtifactUri | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    reference_claim_uris: tuple[ArtifactUri, ...] = ()
    evidence_uris: tuple[ArtifactUri, ...] = ()
    seed: StrictInt = 0
    max_hypotheses: StrictInt = Field(default=8, ge=1, le=256)
    wall_seconds: StrictInt = Field(default=60, ge=1, le=86_400)
    falsification: FalsificationPlan | None = None

    @model_validator(mode="after")
    def validate_operation_inputs(self) -> Self:
        canonicalize_json(self.constraints)
        requires_verified_source = self.operation in {
            ConjectureOperation.REPAIR,
            ConjectureOperation.PARAMETER_GENERALIZE,
        }
        if requires_verified_source and (
            self.source_uri is None or self.verification_record_uri is None
        ):
            raise ValueError(
                "repair and parameter generalization require a verified source"
            )
        if (
            self.operation is ConjectureOperation.GENERATE
            and self.verification_record_uri is not None
        ):
            raise ValueError(
                "conjecture generation does not accept a source verification record"
            )
        return self


class HypothesisTransformationRecord(ContractModel):
    record_version: Literal["1"] = "1"
    operation: ConjectureOperation
    source_uri: ArtifactUri | None = None
    target_claim_uri: ArtifactUri
    edit: HypothesisEdit
    metrics: dict[str, Any] = Field(default_factory=dict)
    parameter_region: ParameterRegion | None = None
    evidence_uris: tuple[ArtifactUri, ...] = ()
    plugin_id: ArtifactUri
    registry_snapshot_uri: ArtifactUri
    implementation_digest: Sha256Digest
    request_digest: Sha256Digest

    @model_validator(mode="after")
    def require_canonical_metrics(self) -> Self:
        canonicalize_json(self.metrics)
        return self


class HypothesisRecord(ContractModel):
    claim_uri: ArtifactUri
    transformation_uri: ArtifactUri
    novelty: NoveltyAssessment
    verification: Verification = Verification.UNVERIFIED
    parameter_region: ParameterRegion | None = None
    search_experiment_uri: ExperimentUri | None = None
    verified_counterexamples: StrictInt = Field(default=0, ge=0)
    detail: str = ""

    @model_validator(mode="after")
    def remain_a_hypothesis(self) -> Self:
        if self.verification is not Verification.UNVERIFIED:
            raise ValueError("generated statements cannot self-certify")
        if self.verified_counterexamples and self.search_experiment_uri is None:
            raise ValueError(
                "verified counterexample counts require a search experiment"
            )
        return self


class ConjectureWorkflowResult(ContractModel):
    schema_version: Literal["1"] = "1"
    operation: ConjectureOperation | None = None
    execution: Execution
    input: InputValidation
    request_digest: Sha256Digest
    plugin_id: ArtifactUri | None = None
    registry_snapshot_uri: ArtifactUri | None = None
    implementation_digest: Sha256Digest | None = None
    hypotheses: tuple[HypothesisRecord, ...] = ()
    verification: Verification = Verification.UNVERIFIED
    detail: str = ""

    @model_validator(mode="after")
    def workflow_cannot_self_certify(self) -> Self:
        if self.verification is not Verification.UNVERIFIED:
            raise ValueError("conjecture workflows cannot self-certify")
        if self.input.status is InputStatus.ACCEPTED and (
            self.operation is None or self.plugin_id is None
        ):
            raise ValueError(
                "accepted conjecture workflows require operation and plugin identity"
            )
        return self
