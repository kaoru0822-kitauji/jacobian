"""Focused tests for the shared checker evidence codec helper."""

from __future__ import annotations

from pathlib import Path

from jacobian.checker_artifacts import put_witness_envelope
from jacobian.contracts.capabilities import CapabilityRequest
from jacobian.contracts.evidence import (
    EvidenceBindings,
    WitnessEnvelope,
    WitnessRole,
)
from jacobian.kernel import JacobianKernel
from jacobian.store import StoredArtifact


def _witness_schema_uri(kernel: JacobianKernel) -> str:
    return kernel.schemas.register_model(
        name="jacobian.witness-envelope",
        version="1",
        model=WitnessEnvelope,
    )


def _semantics_artifact(kernel: JacobianKernel) -> StoredArtifact:
    return kernel.store.get(kernel.matrix.semantics_uri)


def _claim_and_candidate(
    kernel: JacobianKernel,
) -> tuple[StoredArtifact, StoredArtifact]:
    matrix = {
        "matrix_schema_version": "1",
        "domain": "QQ",
        "entries": [
            [{"num": "1", "den": "1"}, {"num": "2", "den": "1"}],
            [{"num": "3", "den": "1"}, {"num": "4", "den": "1"}],
        ],
    }
    computed = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="matrix.determinant.compute",
            input={"matrix": matrix},
        )
    )
    claim = kernel.store.get(computed.output["matrix_uri"])
    candidate = kernel.store.get(computed.output["determinant_uri"])
    return claim, candidate


def test_put_witness_envelope_binds_digests_and_parents(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim, candidate = _claim_and_candidate(kernel)
    semantics = _semantics_artifact(kernel)
    witness_schema_uri = _witness_schema_uri(kernel)

    result = put_witness_envelope(
        kernel.artifacts,
        witness_schema_uri=witness_schema_uri,
        witness_format="matrix.rational_determinant",
        claim_artifact=claim,
        semantics_artifact=semantics,
        candidate_artifact=candidate,
        payload={
            "matrix_uri": claim.artifact_uri,
            "determinant_uri": candidate.artifact_uri,
        },
        summary="exact rational determinant verification witness",
    )

    stored = kernel.store.get(result.artifact_uri)
    assert stored.manifest.schema_uri == witness_schema_uri
    assert stored.manifest.semantics_uri == semantics.artifact_uri
    assert stored.manifest.parents == (claim.artifact_uri, candidate.artifact_uri)
    witness = WitnessEnvelope.model_validate(stored.payload)
    assert witness.witness_format == "matrix.rational_determinant"
    assert witness.format_version == "1"
    assert witness.role is WitnessRole.SUPPORTS_CLAIM
    assert witness.bindings == EvidenceBindings(
        claim_digest=claim.manifest.object_digest,
        semantics_digest=semantics.manifest.object_digest,
        candidate_digest=candidate.manifest.object_digest,
    )
    assert witness.payload == {
        "matrix_uri": claim.artifact_uri,
        "determinant_uri": candidate.artifact_uri,
    }


def test_put_witness_envelope_parents_order_is_claim_then_candidate(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    claim, candidate = _claim_and_candidate(kernel)
    semantics = _semantics_artifact(kernel)
    witness_schema_uri = _witness_schema_uri(kernel)

    result = put_witness_envelope(
        kernel.artifacts,
        witness_schema_uri=witness_schema_uri,
        witness_format="sat.assignment",
        claim_artifact=claim,
        semantics_artifact=semantics,
        candidate_artifact=candidate,
        payload={
            "cnf_uri": claim.artifact_uri,
            "assignment_uri": candidate.artifact_uri,
        },
        summary="SAT assignment verification witness",
    )

    stored = kernel.store.get(result.artifact_uri)
    assert stored.manifest.parents == (claim.artifact_uri, candidate.artifact_uri)
