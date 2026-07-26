from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityRelationshipStatus,
    CapabilityRequest,
)
from jacobian.kernel import JacobianKernel


def _input(mapping: dict[str, str]) -> dict[str, object]:
    return {
        "left": {
            "vertices": ["a", "b", "c"],
            "edges": [["a", "b"], ["b", "c"]],
        },
        "right": {
            "vertices": ["x", "y", "z"],
            "edges": [["x", "z"], ["y", "z"]],
        },
        "mapping": mapping,
    }


@pytest.mark.integration
def test_graph_isomorphism_verifies_a_valid_bijection(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.isomorphism.verify",
            mode=CapabilityMode.VERIFY,
            input=_input({"a": "x", "b": "z", "c": "y"}),
        )
    )

    assert result.output["is_isomorphism"] is True
    assert result.output["conclusion"] == "TRUE"
    assert result.output["coverage"] == "EXHAUSTIVE"
    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert result.relationships[0].status is CapabilityRelationshipStatus.VERIFIED
    assert result.output["verification_record_uri"] in result.artifact_uris


@pytest.mark.integration
def test_graph_isomorphism_verifies_a_negative_result(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.isomorphism.verify",
            mode=CapabilityMode.VERIFY,
            input=_input({"a": "x", "b": "y", "c": "z"}),
        )
    )

    assert result.output["is_isomorphism"] is False
    assert result.output["conclusion"] == "FALSE"
    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED


def test_graph_isomorphism_is_unavailable_without_reference_checkers(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)

    assert "graph.isomorphism.verify" not in {
        descriptor.capability_id
        for descriptor in kernel.capabilities.catalog().capabilities
    }
