"""Generic application workflows over the existing kernel services."""

from __future__ import annotations

from typing import Any

from jacobian.artifacts import ArtifactService
from jacobian.claims import ClaimValidationService
from jacobian.contracts.evaluation import EvaluationProfile
from jacobian.contracts.evidence import WitnessEnvelope, WitnessRole
from jacobian.contracts.workflows import WitnessVerificationWorkflowResult
from jacobian.evaluation import EvaluationService
from jacobian.references import ReferenceInstallation
from jacobian.store import ArtifactStore
from jacobian.verification import VerificationService
from jacobian.witnesses import WitnessSearchService


class VerificationWorkflowService:
    """Compose exploration and verification without creating new authority."""

    def __init__(
        self,
        store: ArtifactStore,
        artifacts: ArtifactService,
        claims: ClaimValidationService,
        evaluation: EvaluationService,
        witnesses: WitnessSearchService,
        verification: VerificationService,
        references: dict[str, ReferenceInstallation],
    ) -> None:
        self.store = store
        self.artifacts = artifacts
        self.claims = claims
        self.evaluation = evaluation
        self.witnesses = witnesses
        self.verification = verification
        self.references = references

    def verify_witness(
        self,
        *,
        reference_name: str,
        claim_payload: dict[str, Any],
        candidate_payload: dict[str, Any],
        witness_role: WitnessRole,
        profile: EvaluationProfile = EvaluationProfile.FAST,
        seed: int = 0,
        evaluation_wall_seconds: int = 60,
        witness_wall_seconds: int = 300,
    ) -> WitnessVerificationWorkflowResult:
        return self._run_witness(
            reference_name=reference_name,
            claim_payload=claim_payload,
            candidate_payload=candidate_payload,
            witness_role=witness_role,
            profile=profile,
            seed=seed,
            evaluation_wall_seconds=evaluation_wall_seconds,
            witness_wall_seconds=witness_wall_seconds,
            verify=True,
        )

    def explore_witness(
        self,
        *,
        reference_name: str,
        claim_payload: dict[str, Any],
        candidate_payload: dict[str, Any],
        witness_role: WitnessRole,
        profile: EvaluationProfile = EvaluationProfile.FAST,
        seed: int = 0,
        evaluation_wall_seconds: int = 60,
        witness_wall_seconds: int = 300,
    ) -> WitnessVerificationWorkflowResult:
        """Run the fast lane and leave proposed evidence explicitly unverified."""

        return self._run_witness(
            reference_name=reference_name,
            claim_payload=claim_payload,
            candidate_payload=candidate_payload,
            witness_role=witness_role,
            profile=profile,
            seed=seed,
            evaluation_wall_seconds=evaluation_wall_seconds,
            witness_wall_seconds=witness_wall_seconds,
            verify=False,
        )

    def _run_witness(
        self,
        *,
        reference_name: str,
        claim_payload: dict[str, Any],
        candidate_payload: dict[str, Any],
        witness_role: WitnessRole,
        profile: EvaluationProfile,
        seed: int,
        evaluation_wall_seconds: int,
        witness_wall_seconds: int,
        verify: bool,
    ) -> WitnessVerificationWorkflowResult:
        try:
            reference = self.references[reference_name]
        except KeyError as exc:
            raise ValueError(f"unknown reference domain: {reference_name}") from exc
        claim = self.artifacts.put(
            schema_uri=reference.claim_schema_uri,
            semantics_uri=reference.semantics_uri,
            payload=claim_payload,
            summary=f"{reference_name} workflow claim",
        )
        candidate = self.artifacts.put(
            schema_uri=reference.candidate_schema_uri,
            semantics_uri=reference.semantics_uri,
            payload=candidate_payload,
            parents=(claim.artifact_uri,),
            summary=f"{reference_name} workflow candidate",
        )
        validation = self.claims.validate(
            claim_uri=claim.artifact_uri,
            plugin_id=reference.plugin_id,
        )
        if not validation.valid:
            return WitnessVerificationWorkflowResult(
                claim_uri=claim.artifact_uri,
                candidate_uri=candidate.artifact_uri,
                claim_validation=validation,
            )
        evaluation = self.evaluation.evaluate_batch(
            claim_uri=claim.artifact_uri,
            candidate_uris=(candidate.artifact_uri,),
            plugin_id=reference.plugin_id,
            profile=profile,
            seed=seed,
            wall_seconds=evaluation_wall_seconds,
        )
        found = self.witnesses.find(
            claim_uri=claim.artifact_uri,
            candidate_uri=candidate.artifact_uri,
            plugin_id=reference.plugin_id,
            witness_role=witness_role,
            wall_seconds=witness_wall_seconds,
        )
        if found.witness_uri is None:
            return WitnessVerificationWorkflowResult(
                claim_uri=claim.artifact_uri,
                candidate_uri=candidate.artifact_uri,
                claim_validation=validation,
                evaluation=evaluation,
                witness_search=found,
            )
        if not verify:
            return WitnessVerificationWorkflowResult(
                claim_uri=claim.artifact_uri,
                candidate_uri=candidate.artifact_uri,
                claim_validation=validation,
                evaluation=evaluation,
                witness_search=found,
            )
        witness = WitnessEnvelope.model_validate(
            self.store.get(found.witness_uri).payload
        )
        checker_id = reference.witness_checker_ids.get(witness.witness_format)
        if checker_id is None:
            raise ValueError(
                "reference domain has no checker for the discovered witness format"
            )
        verified = self.verification.verify_witness(
            claim_uri=claim.artifact_uri,
            candidate_uri=candidate.artifact_uri,
            witness_uri=found.witness_uri,
            checker_id=checker_id,
        )
        return WitnessVerificationWorkflowResult(
            claim_uri=claim.artifact_uri,
            candidate_uri=candidate.artifact_uri,
            claim_validation=validation,
            evaluation=evaluation,
            witness_search=found,
            verification=verified,
        )
