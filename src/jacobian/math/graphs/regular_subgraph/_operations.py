"""Find a nonempty k-regular subgraph by bounded edge-subset enumeration."""

from __future__ import annotations

from itertools import combinations

from jacobian.math.graphs.regular_subgraph._models import (
    RegularSubgraphRequest,
    RegularSubgraphResult,
)


def compute_k_regular_subgraph(
    request: RegularSubgraphRequest,
) -> RegularSubgraphResult:
    """Return a nonempty k-regular subgraph (vertex set and edge set) or found=false.

    A subgraph is k-regular when every *used* vertex has degree exactly k in the
    selected edge set. We enumerate edge subsets in increasing size order and
    return the first feasible solution. For k=0, any single vertex suffices.
    """

    graph = request.graph
    k = request.k
    vertices = graph.vertices
    n_vertices = len(vertices)
    edges = list(graph.edges)
    n_edges = len(edges)

    vertex_to_idx = {v: i for i, v in enumerate(vertices)}

    # k=0: any single vertex with no edges is a 0-regular subgraph.
    if k == 0 and n_vertices > 0:
        return RegularSubgraphResult(
            graph=graph,
            k=k,
            found=True,
            vertices=(vertices[0],),
            edges=(),
        )

    # Precompute edge endpoints as index pairs.
    edge_pairs: list[tuple[int, int]] = []
    for u, v in edges:
        edge_pairs.append((vertex_to_idx[u], vertex_to_idx[v]))

    # Try edge subsets in increasing size. A nonempty subgraph with at least one
    # vertex of positive degree requires at least k+1 vertices and ceil(k*|V|/2) edges.
    min_edges_needed = (k + 1) * k // 2 if k > 0 else 0

    for edge_count in range(max(1, min_edges_needed), n_edges + 1):
        for edge_combo in combinations(range(n_edges), edge_count):
            selected_edges = [edge_pairs[i] for i in edge_combo]
            used_vertices: set[int] = set()
            for u, v in selected_edges:
                used_vertices.add(u)
                used_vertices.add(v)

            if not used_vertices:
                continue

            # Check k-regularity: every used vertex has degree exactly k.
            degree: dict[int, int] = {}
            for u, v in selected_edges:
                degree[u] = degree.get(u, 0) + 1
                degree[v] = degree.get(v, 0) + 1

            if all(d == k for d in degree.values()):
                # Found a k-regular subgraph.
                used_vertex_labels = tuple(sorted(vertices[i] for i in used_vertices))
                used_edge_list = tuple(
                    tuple(sorted((vertices[u], vertices[v]))) for u, v in selected_edges
                )
                return RegularSubgraphResult(
                    graph=graph,
                    k=k,
                    found=True,
                    vertices=used_vertex_labels,
                    edges=tuple(sorted(used_edge_list)),
                )

    return RegularSubgraphResult(graph=graph, k=k, found=False)
