"""Exact divisibility-incidence graph kernel."""

from __future__ import annotations

from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.graphs.values import SimpleUndirectedGraph
from jacobian.math.number_theory._divisibility_graph_models import (
    MAX_GRAPH_EDGES,
    MAX_TOTAL_FAMILY_SIZE,
    DivisibilityIncidenceGraphRequest,
    DivisibilityIncidenceGraphResult,
)


def _admit_graph(request: DivisibilityIncidenceGraphRequest) -> None:
    if any(int(value) <= 0 for value in (*request.left_family, *request.right_family)):
        raise OperationDomainValidationError(
            location=("left_family", "right_family"),
            code="number_theory.non_positive_family",
            message="family values must be positive integers",
        )
    if len(set(request.left_family)) != len(request.left_family):
        raise OperationDomainValidationError(
            location=("left_family",),
            code="number_theory.duplicate_left_family",
            message="left_family values must be unique",
        )
    if len(set(request.right_family)) != len(request.right_family):
        raise OperationDomainValidationError(
            location=("right_family",),
            code="number_theory.duplicate_right_family",
            message="right_family values must be unique",
        )
    vertex_count = len(request.left_family) + len(request.right_family)
    if vertex_count > MAX_TOTAL_FAMILY_SIZE:
        raise OperationDomainValidationError(
            location=("left_family", "right_family"),
            code="number_theory.graph_vertex_budget",
            message=f"families must contain at most {MAX_TOTAL_FAMILY_SIZE} total values",
        )
    if len(request.left_family) * len(request.right_family) > MAX_GRAPH_EDGES:
        raise OperationDomainValidationError(
            location=("left_family", "right_family"),
            code="number_theory.graph_edge_budget",
            message=f"the incidence graph may contain at most {MAX_GRAPH_EDGES} edges",
        )


def compute_divisibility_incidence_graph(
    request: DivisibilityIncidenceGraphRequest,
) -> DivisibilityIncidenceGraphResult:
    """Build a bipartite simple graph joining l to r iff l divides r.

    Left vertices are labeled 'L{i}' and right vertices 'R{j}'.
    An edge connects L{i} to R{j} exactly when left_family[i] divides right_family[j].
    """
    _admit_graph(request)
    left = request.left_family
    right = request.right_family

    left_labels = [f"L{i}" for i in range(len(left))]
    right_labels = [f"R{i}" for i in range(len(right))]

    vertices = tuple(left_labels + right_labels)
    edges: list[tuple[str, str]] = []

    left_vals = [int(value) for value in left]
    right_vals = [int(r) for r in right]

    for i, lv in enumerate(left_vals):
        for j, rv in enumerate(right_vals):
            if rv % lv == 0:
                edges.append((f"L{i}", f"R{j}"))

    edges.sort()
    return DivisibilityIncidenceGraphResult(
        left_family=tuple(left),
        right_family=tuple(right),
        graph=SimpleUndirectedGraph(vertices=vertices, edges=tuple(edges)),
    )


__all__ = ["compute_divisibility_incidence_graph"]
