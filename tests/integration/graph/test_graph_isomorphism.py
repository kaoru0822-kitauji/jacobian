from __future__ import annotations

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
    CapabilityRelationshipStatus,
    CapabilityRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.kernel import JacobianKernel


def _graph_uri(
    kernel: JacobianKernel,
    *,
    vertices: list[str],
    edges: list[list[str]],
) -> str:
    return kernel.artifacts.put(
        schema_uri=kernel.graph.graph_schema_uri,
        semantics_uri=kernel.graph.semantics_uri,
        payload={
            "graph_schema_version": "1",
            "vertices": vertices,
            "edges": edges,
        },
        summary="graph-isomorphism test input",
    ).artifact_uri


def _input(
    kernel: JacobianKernel,
    mapping: dict[str, str],
) -> dict[str, object]:
    left_graph_uri = _graph_uri(
        kernel,
        vertices=["a", "b", "c"],
        edges=[["a", "b"], ["b", "c"]],
    )
    right_graph_uri = _graph_uri(
        kernel,
        vertices=["x", "y", "z"],
        edges=[["x", "z"], ["y", "z"]],
    )
    return {
        "left_graph_uri": left_graph_uri,
        "right_graph_uri": right_graph_uri,
        "mapping": mapping,
    }


def test_graph_isomorphism_verifies_a_valid_bijection(kernel_with_references) -> None:

    result = kernel_with_references.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.isomorphism.verify",
            mode=CapabilityMode.VERIFY,
            input=_input(kernel_with_references, {"a": "x", "b": "z", "c": "y"}),
        )
    )

    assert result.output["is_isomorphism"] is True
    assert result.output["conclusion"] == "TRUE"
    assert result.output["coverage"] == "EXHAUSTIVE"
    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED
    verified_relationships = [
        relationship
        for relationship in result.relationships
        if relationship.status is CapabilityRelationshipStatus.VERIFIED
    ]
    assert len(verified_relationships) == 1
    assert verified_relationships[0].relation_id == "graph.relation.isomorphic-via"
    assert result.output["verification_record_uri"] in result.artifact_uris


def test_graph_isomorphism_verifies_a_negative_result(kernel_with_references) -> None:

    result = kernel_with_references.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.isomorphism.verify",
            mode=CapabilityMode.VERIFY,
            input=_input(kernel_with_references, {"a": "x", "b": "y", "c": "z"}),
        )
    )

    assert result.output["is_isomorphism"] is False
    assert result.output["conclusion"] == "FALSE"
    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert not any(
        relationship.relation_id == "graph.relation.isomorphic-via"
        for relationship in result.relationships
    )


def test_graph_isomorphism_keeps_checker_rejection_unknown(
    kernel_with_references,
) -> None:
    checker_id = kernel_with_references.graph_isomorphism.checker_id
    assert checker_id is not None
    request_input = _input(kernel_with_references, {"a": "x", "b": "z", "c": "y"})
    kernel_with_references.checkers.revoke(
        checker_id, reason="force fail-closed integration case"
    )

    result = kernel_with_references.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.isomorphism.verify",
            mode=CapabilityMode.VERIFY,
            input=request_input,
        )
    )

    assert result.output["is_isomorphism"] is None
    assert result.output["conclusion"] == "UNKNOWN"
    assert result.output["coverage"] == "UNKNOWN"
    assert result.output["verification_record_uri"] is None
    assert result.assurance.level is CapabilityAssuranceLevel.HEURISTIC
    assert not any(
        relationship.relation_id == "graph.relation.isomorphic-via"
        for relationship in result.relationships
    )


def test_graph_isomorphism_accepts_graph_atlas_artifact_handoff(
    kernel_with_references,
) -> None:
    searched = kernel_with_references.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.search.atlas",
            mode=CapabilityMode.EXPLORE,
            input={"order": 3, "constraints": {"connected": True}, "limit": 1},
        )
    )
    candidate = searched.output["candidates"][0]
    graph_uri = candidate["graph_uri"]
    vertices = candidate["graph"]["vertices"]

    result = kernel_with_references.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.isomorphism.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "left_graph_uri": graph_uri,
                "right_graph_uri": graph_uri,
                "mapping": {vertex: vertex for vertex in vertices},
            },
        )
    )

    assert result.output["conclusion"] == "TRUE"
    assert result.output["left_graph_uri"] == graph_uri
    assert result.output["right_graph_uri"] == graph_uri
    assert graph_uri in result.artifact_uris
    pair = kernel_with_references.store.get(result.output["graph_pair_uri"])
    assert pair.manifest.parents == (graph_uri,)
    assert any(
        relationship.relation_id == "graph.relation.pair-scope"
        and relationship.source_artifact_uris == (graph_uri,)
        for relationship in result.relationships
    )


def test_graph_isomorphism_accepts_valid_unsorted_graph_artifacts(
    kernel_with_references,
) -> None:
    left_graph_uri = _graph_uri(
        kernel_with_references,
        vertices=["c", "a", "b"],
        edges=[["b", "c"], ["a", "b"]],
    )
    right_graph_uri = _graph_uri(
        kernel_with_references,
        vertices=["z", "x", "y"],
        edges=[["y", "z"], ["x", "y"]],
    )

    result = kernel_with_references.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.isomorphism.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "left_graph_uri": left_graph_uri,
                "right_graph_uri": right_graph_uri,
                "mapping": {"a": "x", "b": "y", "c": "z"},
            },
        )
    )

    assert result.output["conclusion"] == "TRUE"
    record = kernel_with_references.store.get(result.output["verification_record_uri"])
    assert left_graph_uri in record.manifest.parents
    assert right_graph_uri in record.manifest.parents


def test_graph_isomorphism_rejects_incompatible_graph_artifact(
    kernel_with_references,
) -> None:
    wrong_artifact = kernel_with_references.artifacts.put(
        schema_uri=kernel_with_references.graph.scope_schema_uri,
        semantics_uri=kernel_with_references.graph.semantics_uri,
        payload={
            "scope_schema_version": "1",
            "source": "networkx.graph_atlas_g",
            "backend_version": "test",
            "order": 3,
            "enumerated_count": 2,
        },
    )
    right_graph_uri = _graph_uri(
        kernel_with_references,
        vertices=["x"],
        edges=[],
    )

    result = kernel_with_references.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.isomorphism.verify",
            mode=CapabilityMode.VERIFY,
            input={
                "left_graph_uri": wrong_artifact.artifact_uri,
                "right_graph_uri": right_graph_uri,
                "mapping": {"x": "x"},
            },
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.diagnostics[0].code == "INCOMPATIBLE_GRAPH_ARTIFACT"
    assert result.diagnostics[0].path == "left_graph_uri"


def test_graph_isomorphism_is_unavailable_without_reference_checkers(
    kernel,
) -> None:

    assert "graph.isomorphism.verify" not in {
        descriptor.capability_id
        for descriptor in kernel.capabilities.catalog().capabilities
    }
