from __future__ import annotations

from pathlib import Path

from jacobian.contracts.evidence import WitnessRole
from jacobian.contracts.results import Conclusion, Verification
from jacobian.kernel import JacobianKernel
from jacobian.references import ReferenceInstallation


def _claim(
    reference: ReferenceInstallation,
    *,
    capabilities: list[str],
) -> dict[str, object]:
    return {
        "claim_schema_version": "1",
        "domain_id": reference.domain_id,
        "domain_version": reference.domain_version,
        "semantics_uri": reference.semantics_uri,
        "quantifiers": [],
        "predicate": {"name": "is_bipartite", "parameters": {}},
        "bounds": {},
        "required_capabilities": capabilities,
        "correspondence_status": "HUMAN_REVIEWED",
    }


def test_verification_workflow_preserves_stage_assurance_and_checker_boundary(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    assert kernel.verification_workflows is not None
    reference = kernel.references["graph_paths"]

    result = kernel.verification_workflows.verify_witness(
        reference_name="graph_paths",
        claim_payload=_claim(reference, capabilities=["Evaluator", "WitnessOracle"]),
        candidate_payload={
            "vertices": ["a", "b", "c", "d"],
            "arcs": [["a", "b"], ["b", "c"], ["c", "d"], ["d", "a"]],
        },
        witness_role=WitnessRole.SUPPORTS_CLAIM,
    )

    assert result.claim_validation.valid is True
    assert result.evaluation is not None
    assert all(
        item.result.assurance.verification is Verification.UNVERIFIED
        for item in result.evaluation.items
    )
    assert result.witness_search is not None
    assert (
        result.witness_search.result.assurance.verification is Verification.UNVERIFIED
    )
    assert result.verification is not None
    assert result.verification.conclusion is Conclusion.TRUE
    assert result.verification.assurance.verification is Verification.VERIFIED
    assert result.verification.verification_record_uri is not None


def test_verification_workflow_stops_after_invalid_claim(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    assert kernel.verification_workflows is not None
    reference = kernel.references["graph_paths"]

    result = kernel.verification_workflows.verify_witness(
        reference_name="graph_paths",
        claim_payload=_claim(reference, capabilities=["HypothesisTransformer"]),
        candidate_payload={
            "vertices": ["a", "b"],
            "arcs": [["a", "b"]],
        },
        witness_role=WitnessRole.SUPPORTS_CLAIM,
    )

    assert result.claim_validation.valid is False
    assert result.evaluation is None
    assert result.witness_search is None
    assert result.verification is None
