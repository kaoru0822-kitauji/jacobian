"""Bounded finite-graph optimization capability tests."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityRequest,
)
from jacobian.kernel import JacobianKernel

pytestmark = pytest.mark.integration


def _payload(graph: nx.Graph[str], **budget: int) -> dict[str, object]:
    return {
        "graph": {
            "vertices": sorted(graph.nodes),
            "edges": [sorted(edge) for edge in graph.edges],
        },
        "resource_budget": {
            "wall_seconds": 5,
            "max_solver_calls": 33,
            "max_order": 32,
            **budget,
        },
    }


def _invoke(
    kernel: JacobianKernel,
    capability_id: str,
    graph: nx.Graph[str],
    **budget: int,
):
    return kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id=capability_id,
            input=_payload(graph, **budget),
        )
    )


@pytest.mark.parametrize(
    ("capability_id", "graph", "optimum", "witness_field", "predicate"),
    (
        (
            "graph.domination.minimum.compute",
            nx.cycle_graph(5, create_using=nx.Graph),
            2,
            "witness_vertices",
            "GRAPH_DOMINATION_MINIMUM_OPTIMALITY",
        ),
        (
            "graph.matching.maximal.minimum.compute",
            nx.cycle_graph(6, create_using=nx.Graph),
            2,
            "witness_edges",
            "GRAPH_MINIMUM_MAXIMAL_MATCHING_OPTIMALITY",
        ),
        (
            "graph.induced_forest.maximum.compute",
            nx.complete_graph(4, create_using=nx.Graph),
            2,
            "witness_vertices",
            "GRAPH_INDUCED_FOREST_MAXIMUM_OPTIMALITY",
        ),
        (
            "graph.induced_tree.maximum.compute",
            nx.cycle_graph(4, create_using=nx.Graph),
            3,
            "witness_vertices",
            "GRAPH_INDUCED_TREE_MAXIMUM_OPTIMALITY",
        ),
        (
            "graph.induced_bipartite.maximum.compute",
            nx.complete_graph(5, create_using=nx.Graph),
            2,
            "witness_vertices",
            "GRAPH_INDUCED_BIPARTITE_MAXIMUM_OPTIMALITY",
        ),
    ),
)
def test_graph_optimizer_returns_exact_witness_and_open_obligation(
    tmp_path: Path,
    capability_id: str,
    graph: nx.Graph[int],
    optimum: int,
    witness_field: str,
    predicate: str,
) -> None:
    relabeled = nx.relabel_nodes(graph, lambda vertex: f"v{vertex}")
    kernel = JacobianKernel(tmp_path)

    result = _invoke(kernel, capability_id, relabeled)

    assert result.output["status"] == "EXACT"
    assert result.output["optimum_value"] == optimum
    assert result.output["lower_bound"] == optimum
    assert result.output["upper_bound"] == optimum
    assert len(result.output[witness_field]) == optimum
    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert len(result.artifact_uris) == 3
    input_uri, result_uri, obligation_uri = result.artifact_uris
    assert kernel.store.get(result_uri).manifest.parents == (input_uri,)
    obligation = kernel.store.get(obligation_uri)
    assert frozenset(obligation.manifest.parents) == frozenset((input_uri, result_uri))
    assert obligation.payload["predicate"] == predicate
    assert result.obligations[0].obligation_uri == obligation_uri
    if capability_id == "graph.domination.minimum.compute":
        assert nx.is_dominating_set(relabeled, result.output["witness_vertices"])
    elif capability_id == "graph.matching.maximal.minimum.compute":
        matching = {tuple(edge) for edge in result.output["witness_edges"]}
        assert nx.is_matching(relabeled, matching)
        assert nx.is_maximal_matching(relabeled, matching)
    else:
        induced = relabeled.subgraph(result.output["witness_vertices"])
        if capability_id == "graph.induced_forest.maximum.compute":
            assert nx.is_forest(induced)
        elif capability_id == "graph.induced_tree.maximum.compute":
            assert nx.is_tree(induced)
        else:
            assert nx.is_bipartite(induced)


def test_solver_call_budget_preserves_incumbent_without_claiming_optimum(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    graph = nx.relabel_nodes(nx.complete_graph(5), lambda vertex: f"v{vertex}")

    result = _invoke(
        kernel,
        "graph.induced_forest.maximum.compute",
        graph,
        max_solver_calls=1,
    )

    assert result.output["status"] == "UNKNOWN"
    assert result.output["optimum_value"] is None
    assert result.output["termination_reason"] == "SOLVER_CALL_LIMIT"
    assert result.output["lower_bound"] == 1
    assert result.output["upper_bound"] == 4
    assert len(result.output["witness_vertices"]) == 1
    assert result.completeness.status is CapabilityCompletenessStatus.UNKNOWN
    obligation = kernel.store.get(result.artifact_uris[2])
    assert obligation.payload["claimed_value"] is None


@pytest.mark.parametrize(
    "capability_id",
    (
        "graph.domination.minimum.compute",
        "graph.matching.maximal.minimum.compute",
        "graph.induced_forest.maximum.compute",
        "graph.induced_tree.maximum.compute",
        "graph.induced_bipartite.maximum.compute",
    ),
)
def test_empty_graph_boundary_is_exact_zero(
    tmp_path: Path,
    capability_id: str,
) -> None:
    kernel = JacobianKernel(tmp_path)
    result = _invoke(kernel, capability_id, nx.Graph())

    assert result.output["status"] == "EXACT"
    assert result.output["optimum_value"] == 0
    assert result.output["incumbent_value"] == 0
    assert result.output["termination_reason"] == "SPECIAL_CASE"


def test_order_budget_fails_before_artifact_writes(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    graph = nx.relabel_nodes(nx.path_graph(3), lambda vertex: f"v{vertex}")

    result = _invoke(
        kernel,
        "graph.domination.minimum.compute",
        graph,
        max_order=2,
    )

    assert result.execution.status.value == "ERROR"
    assert result.diagnostics[0].code == "INVALID_GRAPH_OPTIMIZATION_REQUEST"
    assert result.artifact_uris == ()
