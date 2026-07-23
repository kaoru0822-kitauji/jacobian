from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.artifacts import ArtifactValidationError
from jacobian.kernel import JacobianKernel


def _claim_payload(
    *,
    domain_id: str,
    semantics_uri: str,
    predicate: str,
    parameters: dict[str, object],
) -> dict[str, object]:
    return {
        "claim_schema_version": "1",
        "domain_id": domain_id,
        "domain_version": "1",
        "semantics_uri": semantics_uri,
        "quantifiers": [],
        "predicate": {
            "name": predicate,
            "parameters": parameters,
        },
        "bounds": {},
        "required_capabilities": [],
        "correspondence_status": "UNREVIEWED",
    }


@pytest.mark.contract
def test_path_closure_claim_requires_simple_path_semantics(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    reference = kernel.references["graph_paths"]

    with pytest.raises(ArtifactValidationError, match="simple"):
        kernel.artifacts.put(
            schema_uri=reference.claim_schema_uri,
            semantics_uri=reference.semantics_uri,
            payload=_claim_payload(
                domain_id="jacobian.graph-paths",
                semantics_uri=reference.semantics_uri,
                predicate="intended_paths_complete",
                parameters={},
            ),
        )


@pytest.mark.contract
def test_maxdet_claim_requires_a_bounded_matrix_scope(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    reference = kernel.references["matrices"]

    with pytest.raises(ArtifactValidationError, match="scope"):
        kernel.artifacts.put(
            schema_uri=reference.claim_schema_uri,
            semantics_uri=reference.semantics_uri,
            payload=_claim_payload(
                domain_id="jacobian.integer-matrices",
                semantics_uri=reference.semantics_uri,
                predicate="maximize_absolute_determinant",
                parameters={},
            ),
        )


@pytest.mark.contract
def test_graph_candidate_schema_rejects_incomplete_arc(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    reference = kernel.references["graph_paths"]

    with pytest.raises(ArtifactValidationError):
        kernel.artifacts.put(
            schema_uri=reference.candidate_schema_uri,
            semantics_uri=reference.semantics_uri,
            payload={
                "vertices": ["s", "t"],
                "arcs": [["s"]],
            },
        )
