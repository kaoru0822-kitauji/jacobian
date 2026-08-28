"""Domain adapter for tree-decomposition operations."""

from __future__ import annotations

from jacobian.math.graphs.tree_decompositions._models import (
    AdhesionsRequest,
    AdhesionsResult,
    BagIntersectionGraphRequest,
    BagIntersectionGraphResult,
    RerootRequest,
    RerootResult,
    RestrictRequest,
    RestrictResult,
    VertexOccurrencesRequest,
    VertexOccurrencesResult,
    WidthRequest,
    WidthResult,
)
from jacobian.math.graphs.tree_decompositions.operations import (
    adhesions,
    bag_intersection_graph,
    reroot,
    restrict,
    vertex_occurrences,
    width,
)

__all__ = [
    "compute_adhesions",
    "compute_bag_intersection_graph",
    "compute_reroot",
    "compute_restrict",
    "compute_vertex_occurrences",
    "compute_width",
]


def compute_width(request: WidthRequest) -> WidthResult:
    return width(request.decomposition)


def compute_vertex_occurrences(
    request: VertexOccurrencesRequest,
) -> VertexOccurrencesResult:
    result = vertex_occurrences(request.decomposition)
    return VertexOccurrencesResult(
        per_vertex={vertex: dict(profile) for vertex, profile in result.items()}
    )


def compute_adhesions(request: AdhesionsRequest) -> AdhesionsResult:
    result = adhesions(request.decomposition)
    return AdhesionsResult(
        edges=tuple(dict(edge) for edge in result["edges"]),
        max_adhesion=result["max_adhesion"],
        size_profile=result["size_profile"],
    )


def compute_reroot(request: RerootRequest) -> RerootResult:
    return reroot(request.decomposition, request.root)


def compute_restrict(request: RestrictRequest) -> RestrictResult:
    result = restrict(request.decomposition, frozenset(request.subset))
    return RestrictResult(
        graph=dict(result["graph"]),
        tree_nodes=result["tree_nodes"],
        tree_edges=result["tree_edges"],
        bags=result["bags"],
    )


def compute_bag_intersection_graph(
    request: BagIntersectionGraphRequest,
) -> BagIntersectionGraphResult:
    result = bag_intersection_graph(request.decomposition)
    return BagIntersectionGraphResult(
        nodes=tuple(dict(node) for node in result["nodes"]),
        edges=tuple(dict(edge) for edge in result["edges"]),
        max_adhesion=result["max_adhesion"],
    )
