from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityRequest,
)
from jacobian.contracts.graph_invariant_operations import GraphDistanceMatrixResult
from jacobian.contracts.results import ExecutionStatus


def _invoke(kernel, vertices: list[str], edges: list[list[str]]):
    return kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="graph.distance_matrix.compute",
            input={"graph": {"vertices": vertices, "edges": edges}},
        )
    )


def _result(**changes: object) -> GraphDistanceMatrixResult:
    values: dict[str, object] = {
        "semantics_version": "unweighted-shortest-path-distance-matrix.v1",
        "vertex_ordering": "LEXICOGRAPHIC_ASCENDING",
        "pair_coverage": "ALL_ORDERED_VERTEX_PAIRS",
        "unreachable_representation": "JSON_NULL",
        "vertices": ("a", "b", "c"),
        "distances": ((0, 1, 2), (1, 0, 1), (2, 1, 0)),
        "connected": True,
    }
    values.update(changes)
    return GraphDistanceMatrixResult.model_validate(values)


def test_distance_matrix_is_complete_canonical_and_lineage_bound(kernel) -> None:
    result = _invoke(
        kernel,
        ["c", "a", "b"],
        [["a", "b"], ["b", "c"]],
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.output["result"] == {
        "semantics_version": "unweighted-shortest-path-distance-matrix.v1",
        "vertex_ordering": "LEXICOGRAPHIC_ASCENDING",
        "pair_coverage": "ALL_ORDERED_VERTEX_PAIRS",
        "unreachable_representation": "JSON_NULL",
        "vertices": ["a", "b", "c"],
        "distances": [[0, 1, 2], [1, 0, 1], [2, 1, 0]],
        "connected": True,
    }
    assert len(result.artifact_uris) == 2
    input_uri, matrix_uri = result.artifact_uris
    assert kernel.store.get(matrix_uri).manifest.parents == (input_uri,)
    assert result.relationships[0].relation_id == "graph.distance_matrix.relation"
    assert result.relationships[0].source_artifact_uris == (input_uri,)
    assert result.relationships[0].target_artifact_uris == (matrix_uri,)


def test_distance_matrix_represents_disconnected_pairs_with_null(kernel) -> None:
    result = _invoke(kernel, ["c", "a", "b"], [["a", "b"]])

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["result"]["vertices"] == ["a", "b", "c"]
    assert result.output["result"]["distances"] == [
        [0, 1, None],
        [1, 0, None],
        [None, None, 0],
    ]
    assert result.output["result"]["connected"] is False


def test_distance_matrix_empty_and_singleton_conventions(kernel) -> None:
    empty = _invoke(kernel, [], [])
    singleton = _invoke(kernel, ["only"], [])

    assert empty.output["result"]["vertices"] == []
    assert empty.output["result"]["distances"] == []
    assert empty.output["result"]["connected"] is False
    assert singleton.output["result"]["vertices"] == ["only"]
    assert singleton.output["result"]["distances"] == [[0]]
    assert singleton.output["result"]["connected"] is True


def test_distance_matrix_rejects_graph_above_existing_order_bound(kernel) -> None:
    result = _invoke(kernel, [f"v{index:02d}" for index in range(33)], [])

    assert result.execution.status is ExecutionStatus.ERROR
    assert result.artifact_uris == ()
    assert result.diagnostics[0].code == "INVALID_REQUEST"


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        ({"vertices": ("b", "a", "c")}, "unique and sorted"),
        ({"distances": ((0, 1), (1, 0))}, "square"),
        (
            {"distances": ((1, 1, 2), (1, 0, 1), (2, 1, 0))},
            "diagonal",
        ),
        (
            {"distances": ((0, 0, 2), (0, 0, 1), (2, 1, 0))},
            "off-diagonal",
        ),
        (
            {"distances": ((0, 1, 2), (2, 0, 1), (2, 1, 0))},
            "symmetric",
        ),
        (
            {"distances": ((0, 1, 3), (1, 0, 1), (3, 1, 0))},
            "triangle inequality",
        ),
        (
            {"distances": ((0, 1, None), (1, 0, 1), (None, 1, 0))},
            "component closure",
        ),
        ({"connected": False}, "connected"),
    ),
)
def test_distance_matrix_result_rejects_inconsistent_claims(
    changes: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        _result(**changes)


def test_distance_matrix_public_postdoc_graph(kernel) -> None:
    result = _invoke(
        kernel,
        ["0", "1", "2", "3", "4", "5"],
        [["0", "3"], ["0", "4"], ["1", "4"], ["2", "4"], ["3", "4"], ["3", "5"]],
    )

    assert result.execution.status is ExecutionStatus.COMPLETED
    assert result.output["result"]["distances"] == [
        [0, 2, 2, 1, 1, 2],
        [2, 0, 2, 2, 1, 3],
        [2, 2, 0, 2, 1, 3],
        [1, 2, 2, 0, 1, 1],
        [1, 1, 1, 1, 0, 2],
        [2, 3, 3, 1, 2, 0],
    ]
    assert result.output["result"]["connected"] is True
