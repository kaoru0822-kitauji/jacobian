"""Application-level workflows composed from existing trust-boundary services."""

from __future__ import annotations

from typing import Literal

from jacobian.contracts.claims import ClaimValidationResult
from jacobian.contracts.common import ArtifactUri
from jacobian.contracts.evaluation import EvaluationBatchResult
from jacobian.contracts.results import ContractModel, ResultEnvelope
from jacobian.contracts.witness_search import WitnessFindResult


class WitnessVerificationWorkflowResult(ContractModel):
    schema_version: Literal["1"] = "1"
    claim_uri: ArtifactUri
    candidate_uri: ArtifactUri
    claim_validation: ClaimValidationResult
    evaluation: EvaluationBatchResult | None = None
    witness_search: WitnessFindResult | None = None
    verification: ResultEnvelope | None = None
