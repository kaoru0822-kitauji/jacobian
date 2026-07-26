from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityMode,
    CapabilityRelationshipStatus,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel

pytestmark = pytest.mark.usefixtures("initialized_kernel_store")


@pytest.mark.integration
def test_graph_atlas_search_is_bounded_complete_and_replayable(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.search.atlas",
            input={
                "order": 5,
                "constraints": {
                    "connected": True,
                    "triangle_free": True,
                    "independence_number": 3,
                },
                "limit": 2,
            },
        )
    )

    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE
    assert result.completeness.assurance_level is CapabilityAssuranceLevel.COMPUTED
    assert result.scope is not None
    assert result.scope.artifact_uri in result.artifact_uris
    assert result.output["match_count"] >= result.output["returned_count"] == 2
    assert result.output["truncated"] is (
        result.output["match_count"] > result.output["returned_count"]
    )
    assert "conclusion" not in result.output

    for candidate in result.output["candidates"]:
        graph_uri = candidate["graph_uri"]
        graph = kernel.store.get(graph_uri)
        assert candidate["graph"] == graph.payload
        assert graph.payload["graph_schema_version"] == "1"
        assert len(graph.payload["vertices"]) == 5
        assert candidate["properties"]["connected"] is True
        assert candidate["properties"]["triangle_count"] == 0
        assert candidate["properties"]["independence_number"] == 3

    scope = kernel.store.get(result.scope.artifact_uri)
    assert scope.payload["source"] == "networkx.graph_atlas_g"
    assert scope.payload["order"] == 5
    assert scope.payload["enumerated_count"] > 0


@pytest.mark.integration
def test_graph_atlas_search_reports_no_match_without_a_truth_claim(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.search.atlas",
            input={
                "order": 4,
                "constraints": {
                    "tree": True,
                    "minimum_edges": 6,
                },
                "limit": 1,
            },
        )
    )

    assert result.output["match_count"] == 0
    assert result.output["candidates"] == []
    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert "conclusion" not in result.output


@pytest.mark.integration
def test_graph_capabilities_return_actionable_parameter_and_artifact_errors(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    invalid_range = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.search.atlas",
            input={
                "order": 5,
                "constraints": {
                    "minimum_edges": 5,
                    "maximum_edges": 4,
                },
            },
        )
    )
    assert invalid_range.execution.status is ExecutionStatus.ERROR
    assert invalid_range.diagnostics[0].code == "INVALID_CONSTRAINT_RANGE"
    assert invalid_range.diagnostics[0].path == "constraints/minimum_edges"
    assert invalid_range.episode_uri is None

    missing_graph = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.compute.properties",
            input={
                "graph_uri": "artifact://sha256/" + "f" * 64,
                "properties": ["order"],
            },
        )
    )
    assert missing_graph.execution.status is ExecutionStatus.ERROR
    assert missing_graph.diagnostics[0].code == "GRAPH_ARTIFACT_NOT_FOUND"
    assert missing_graph.episode_uri is None


@pytest.mark.integration
def test_graph_property_batch_materializes_exact_computed_artifact(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)
    searched = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.search.atlas",
            input={
                "order": 5,
                "constraints": {"tree": True, "maximum_degree": 2},
                "limit": 1,
            },
        )
    )
    graph_uri = searched.output["candidates"][0]["graph_uri"]

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.compute.properties",
            mode=CapabilityMode.EXPLORE,
            input={
                "graph_uri": graph_uri,
                "properties": [
                    "order",
                    "size",
                    "connected",
                    "bipartite",
                    "degree_sequence",
                    "triangle_count",
                    "independence_number",
                ],
            },
        )
    )

    assert result.output["graph_uri"] == graph_uri
    assert result.output["properties"] == {
        "bipartite": {
            "backend": "networkx",
            "exactness": "EXACT",
            "value": True,
        },
        "connected": {
            "backend": "networkx",
            "exactness": "EXACT",
            "value": True,
        },
        "degree_sequence": {
            "backend": "networkx",
            "exactness": "EXACT",
            "value": [2, 2, 2, 1, 1],
        },
        "independence_number": {
            "backend": "networkx.max_weight_clique(complement)",
            "exactness": "EXACT",
            "value": 3,
        },
        "order": {
            "backend": "networkx",
            "exactness": "EXACT",
            "value": 5,
        },
        "size": {
            "backend": "networkx",
            "exactness": "EXACT",
            "value": 4,
        },
        "triangle_count": {
            "backend": "networkx",
            "exactness": "EXACT",
            "value": 0,
        },
    }
    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert len(result.relationships) == 1
    relationship = result.relationships[0]
    assert relationship.status is CapabilityRelationshipStatus.PROPOSED
    assert relationship.source_artifact_uris == (graph_uri,)
    assert relationship.target_artifact_uris == (
        result.output["property_artifact_uri"],
    )
    property_artifact = kernel.store.get(result.output["property_artifact_uri"])
    assert property_artifact.manifest.parents == (graph_uri,)
