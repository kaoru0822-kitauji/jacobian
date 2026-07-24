"""Pinned Lean certificate construction and verification."""

from __future__ import annotations

import hashlib

from jacobian.artifacts import ArtifactService
from jacobian.canonical import canonicalize_json
from jacobian.contracts.evidence import CertificateEnvelope, EvidenceBindings
from jacobian.contracts.lean import (
    LeanCandidate,
    LeanClaim,
    LeanEnvironment,
    LeanVerifyResult,
)
from jacobian.references import LeanCheckerInstallation
from jacobian.store import ArtifactStore
from jacobian.verification import VerificationService


class LeanService:
    """Build one fully bound Lean certificate and replay its authorized checker."""

    def __init__(
        self,
        store: ArtifactStore,
        artifacts: ArtifactService,
        verification: VerificationService,
        installations: dict[LeanEnvironment, LeanCheckerInstallation],
    ) -> None:
        self.store = store
        self.artifacts = artifacts
        self.verification = verification
        self.installations = installations

    def verify(
        self,
        *,
        statement: str,
        proof: str,
        environment: LeanEnvironment = LeanEnvironment.CORE,
    ) -> LeanVerifyResult:
        installation = self.installations[environment]
        claim_payload = LeanClaim(
            environment=environment,
            statement=statement,
            allowed_axioms=installation.allowed_axioms,
        )
        candidate_payload = LeanCandidate(
            environment=environment,
            statement=statement,
            proof=proof,
        )
        claim = self.artifacts.put(
            schema_uri=installation.claim_schema_uri,
            semantics_uri=installation.semantics_uri,
            payload=claim_payload.model_dump(mode="json"),
            summary="exact Lean proposition",
        )
        candidate = self.artifacts.put(
            schema_uri=installation.candidate_schema_uri,
            semantics_uri=installation.semantics_uri,
            payload=candidate_payload.model_dump(mode="json"),
            parents=(claim.artifact_uri,),
            summary=f"proposed {environment.value} Lean proof",
        )
        claim_artifact = self.store.get(claim.artifact_uri)
        candidate_artifact = self.store.get(candidate.artifact_uri)
        semantics = self.store.get(installation.semantics_uri)
        bindings = EvidenceBindings(
            claim_digest=claim_artifact.manifest.object_digest,
            semantics_digest=semantics.manifest.object_digest,
            candidate_digest=candidate_artifact.manifest.object_digest,
        )
        certificate_payload = {
            "statement": statement,
            "proof": proof,
            "environment": environment.value,
            "declaration_name": "jacobian_theorem",
            "lean_version": installation.lean_version,
            "lean_commit": installation.lean_commit,
            "import_name": installation.import_name,
            "mathlib_commit": installation.mathlib_commit,
            "allowed_axioms": list(installation.allowed_axioms),
        }
        payload_digest = (
            "sha256:"
            + hashlib.sha256(canonicalize_json(certificate_payload)).hexdigest()
        )
        certificate_envelope = CertificateEnvelope(
            certificate_type="lean4.kernel",
            format_version="1",
            bindings=bindings,
            payload_digest=payload_digest,
            payload=certificate_payload,
        )
        certificate = self.artifacts.put(
            schema_uri=installation.certificate_schema_uri,
            semantics_uri=installation.semantics_uri,
            payload=certificate_envelope.model_dump(mode="json"),
            parents=(claim.artifact_uri, candidate.artifact_uri),
            summary=f"{environment.value} Lean proof certificate",
        )
        result = self.verification.verify_certificate(
            certificate_uri=certificate.artifact_uri,
            timeout_seconds=installation.checker_timeout_seconds,
        )
        return LeanVerifyResult(
            claim_uri=claim.artifact_uri,
            candidate_uri=candidate.artifact_uri,
            certificate_uri=certificate.artifact_uri,
            result=result,
        )
