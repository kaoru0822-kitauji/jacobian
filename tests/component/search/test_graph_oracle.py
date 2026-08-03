from __future__ import annotations

import pytest

from jacobian.eval.graph_oracle import (
    GraphOracleError,
    check_constraints,
    check_reported_properties,
    compute_properties,
)


def test_graph_oracle_computes_path_properties_without_networkx() -> None:
    graph = {
        "vertices": ["a", "b", "c", "d", "e", "f"],
        "edges": [["a", "b"], ["b", "c"], ["c", "d"], ["d", "e"], ["e", "f"]],
    }

    properties = compute_properties(graph)

    assert properties == {
        "order": 6,
        "size": 5,
        "connected": True,
        "bipartite": True,
        "tree": True,
        "triangle_count": 0,
        "minimum_degree": 1,
        "maximum_degree": 2,
        "degree_sequence": [2, 2, 2, 2, 1, 1],
        "independence_number": 3,
    }
    check_constraints(
        properties,
        {"connected": True, "tree": True, "maximum_degree": 2},
    )
    check_reported_properties(
        properties,
        {"order": 6, "tree": True, "independence_number": 3},
        ["order", "tree", "independence_number"],
    )


def test_graph_oracle_rejects_wrong_exact_property() -> None:
    properties = compute_properties({"vertices": ["a", "b"], "edges": [["a", "b"]]})

    with pytest.raises(GraphOracleError, match="differs from hidden oracle"):
        check_reported_properties(
            properties,
            {"order": {"value": 3, "exactness": "EXACT"}},
            ["order"],
        )


def test_graph_oracle_accepts_maximum_independence_scope() -> None:
    graph = {"vertices": [str(index) for index in range(18)], "edges": []}

    properties = compute_properties(graph)

    assert properties["order"] == 18
    assert properties["independence_number"] == 18


def test_graph_oracle_rejects_exponential_independence_scope() -> None:
    graph = {"vertices": [str(index) for index in range(19)], "edges": []}

    with pytest.raises(GraphOracleError, match="at most 18 vertices"):
        compute_properties(graph)
