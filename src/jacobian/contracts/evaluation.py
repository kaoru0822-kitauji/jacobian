"""Wire contracts for untrusted batched candidate evaluation."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import Field, StrictInt, model_validator

from jacobian.canonical import canonicalize_json
from jacobian.contracts.common import ArtifactUri, Sha256Digest
from jacobian.contracts.results import (
    Arithmetic,
    Conclusion,
    ContractModel,
    Coverage,
    Execution,
    InputValidation,
    Method,
    ResultEnvelope,
)


class EvaluationProfile(StrEnum):
    FAST = "FAST"
    EXACT_CANDIDATE = "EXACT_CANDIDATE"


class PluginEvaluationResponse(ContractModel):
    """Untrusted response returned by a domain evaluator capability."""

    response_version: Literal["1"] = "1"
    conclusion: Conclusion
    arithmetic: Arithmetic
    method: Method
    coverage: Coverage
    objectives: dict[str, Any] = Field(default_factory=dict)
    features: dict[str, Any] = Field(default_factory=dict)
    failure_classifications: tuple[str, ...] = ()
    detail: str = ""

    @model_validator(mode="after")
    def require_canonical_data(self) -> Self:
        canonicalize_json(self.objectives)
        canonicalize_json(self.features)
        return self


class EvaluationItem(ContractModel):
    candidate_uri: ArtifactUri
    result: ResultEnvelope
    objectives: dict[str, Any] = Field(default_factory=dict)
    features: dict[str, Any] = Field(default_factory=dict)
    failure_classifications: tuple[str, ...] = ()
    detail: str = ""


class EvaluationBatchResult(ContractModel):
    schema_version: Literal["1"] = "1"
    execution: Execution
    input: InputValidation
    claim_uri: ArtifactUri
    plugin_id: ArtifactUri
    profile: EvaluationProfile
    seed: StrictInt
    evaluator_digest: Sha256Digest | None = None
    environment_digest: Sha256Digest | None = None
    items: tuple[EvaluationItem, ...] = ()
