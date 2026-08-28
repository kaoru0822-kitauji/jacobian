"""Domain adapter for tree-decomposition operations."""

from __future__ import annotations

from jacobian.canonical import CanonicalLimits
from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.graphs.decomposition.tree_decompositions._models import (
    AdhesionsRequest,
    AdhesionsResult,
    BagIntersectionGraphRequest,
    BagIntersectionGraphResult,
    RerootRequest,
    RerootResult,
    RestrictRequest,
    VertexOccurrencesRequest,
    VertexOccurrencesResult,
    WidthRequest,
    WidthResult,
    _normalized_tree_nodes,
    _reroot_result_wire_bytes,
)
from jacobian.math.graphs.decomposition.tree_decompositions.operations import (
    adhesions,
    bag_intersection_graph,
    reroot,
    restrict,
    vertex_occurrences,
    width,
)
from jacobian.math.graphs.decomposition.tree_decompositions.values import (
    TreeDecomposition,
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
    return vertex_occurrences(request.decomposition)


def compute_adhesions(request: AdhesionsRequest) -> AdhesionsResult:
    return adhesions(request.decomposition)


def compute_reroot(request: RerootRequest) -> RerootResult:
    if request.root not in request.decomposition.tree_nodes:
        raise OperationDomainValidationError(
            location=("root",),
            code="graph.root_must_be_a_declared_tree_node",
            message="root must be a declared tree node",
        )
    normalized_nodes = _normalized_tree_nodes(request.decomposition)
    if len(set(normalized_nodes)) != len(normalized_nodes):
        raise OperationDomainValidationError(
            location=("decomposition", "tree_nodes"),
            code="graph.reroot_tree_node_labels_collide_after_normalization",
            message="tree node labels collide after Unicode NFC normalization",
        )
    output_limit = CanonicalLimits().max_output_bytes
    if _reroot_result_wire_bytes(request.decomposition, request.root) > output_limit:
        raise OperationDomainValidationError(
            location=("decomposition", "tree_nodes"),
            code="graph.reroot_result_exceeds_transport_limit",
            message="rerooted tree-decomposition paths exceed the "
            f"{output_limit}-byte canonical output limit",
        )
    return reroot(request.decomposition, request.root)


def compute_restrict(request: RestrictRequest) -> TreeDecomposition:
    if not set(request.subset).issubset(request.decomposition.graph.vertices):
        raise OperationDomainValidationError(
            location=("subset",),
            code="graph.subset_must_contain_only_declared_source_vertice",
            message="subset must contain only declared source vertices",
        )
    return restrict(request.decomposition, frozenset(request.subset))


def compute_bag_intersection_graph(
    request: BagIntersectionGraphRequest,
) -> BagIntersectionGraphResult:
    return bag_intersection_graph(request.decomposition)
