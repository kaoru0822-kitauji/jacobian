"""Shared producer-side semantics for finite graph k-colorability."""

from __future__ import annotations

from jacobian.contracts.graph_coloring import ChromaticGraph


def canonical_graph(graph: ChromaticGraph) -> ChromaticGraph:
    """Normalize vertex and undirected edge order for stable artifacts."""

    edges = tuple(
        sorted(
            (min(edge_left, edge_right), max(edge_left, edge_right))
            for edge_left, edge_right in graph.edges
        )
    )
    return ChromaticGraph(vertices=tuple(sorted(graph.vertices)), edges=edges)


def coloring_cnf(
    graph: ChromaticGraph,
    colors: int,
) -> tuple[tuple[str, ...], tuple[tuple[int, ...], ...]]:
    """Build exactly-one and edge-separation clauses for one graph and k."""

    variable_names = tuple(
        f"v{vertex:02d}_c{color:02d}"
        for vertex in range(len(graph.vertices))
        for color in range(colors)
    )

    def variable(vertex: int, color: int) -> int:
        return vertex * colors + color + 1

    clauses: list[tuple[int, ...]] = []
    for vertex in range(len(graph.vertices)):
        clauses.append(tuple(variable(vertex, color) for color in range(colors)))
        for color_left in range(colors):
            for color_right in range(color_left + 1, colors):
                clauses.append(
                    (-variable(vertex, color_left), -variable(vertex, color_right))
                )
    vertex_index = {vertex: index for index, vertex in enumerate(graph.vertices)}
    for edge_left, edge_right in graph.edges:
        for color in range(colors):
            clauses.append(
                (
                    -variable(vertex_index[edge_left], color),
                    -variable(vertex_index[edge_right], color),
                )
            )
    return variable_names, tuple(clauses)
