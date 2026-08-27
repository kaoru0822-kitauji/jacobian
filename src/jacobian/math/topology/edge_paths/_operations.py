"""Domain functions for algebraic topology operations."""

from __future__ import annotations

from jacobian.math.topology.edge_paths._models import (
    EdgePathConcatenateRequest,
    EdgePathConcatenateResult,
    EdgePathWordRequest,
    EdgePathWordResult,
)


def _admit_edge_path_word(request: EdgePathWordRequest) -> None:
    for u, v in request.edges:
        if not (0 <= u < request.vertex_count and 0 <= v < request.vertex_count):
            raise ValueError("edge vertices must be in 0..vertex_count-1")
    if not 0 <= request.start_vertex < request.vertex_count:
        raise ValueError("start vertex must be in 0..vertex_count-1")
    current = request.start_vertex
    for step in request.path:
        if step.edge_index >= len(request.edges):
            raise ValueError("path edge index is outside the graph")
        left, right = request.edges[step.edge_index]
        source, target = (left, right) if step.orientation == 1 else (right, left)
        if source != current:
            raise ValueError("oriented edge path is not continuous")
        current = target


def _admit_edge_path_concatenation(request: EdgePathConcatenateRequest) -> None:
    if any(not 0 <= v < request.vertex_count for v in request.path_a):
        raise ValueError("path_a vertices must be valid")
    if any(not 0 <= v < request.vertex_count for v in request.path_b):
        raise ValueError("path_b vertices must be valid")
    if request.path_a[-1] != request.path_b[0]:
        raise ValueError("concatenated paths must share their endpoint")


def compute_edge_path_word(request: EdgePathWordRequest) -> EdgePathWordResult:
    """Compute the free group word for an edge path.

    Each edge in the graph is assigned a generator label e_i.
    Traversing edge i forward adds e_i, backward adds e_i^{-1}.
    """
    _admit_edge_path_word(request)
    word = [
        f"e{step.edge_index + 1}" + ("" if step.orientation == 1 else "^-1")
        for step in request.path
    ]
    return EdgePathWordResult(
        word=tuple(word),
        length=len(word),
    )


def compute_edge_path_concatenate(
    request: EdgePathConcatenateRequest,
) -> EdgePathConcatenateResult:
    """Concatenate two edge paths.

    If the last vertex of path_a equals the first vertex of path_b,
    the concatenation is path_a + path_b[1:], removing the duplicate.
    """
    _admit_edge_path_concatenation(request)
    path_a = list(request.path_a)
    path_b = list(request.path_b)
    if path_a and path_b and path_a[-1] == path_b[0]:
        result = path_a + path_b[1:]
    else:
        result = path_a + path_b
    return EdgePathConcatenateResult(
        path=tuple(result),
        length=len(result),
    )
