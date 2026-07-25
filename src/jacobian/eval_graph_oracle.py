"""Independent standard-library oracle for small undirected graph evaluations."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from itertools import combinations
from typing import Any


class GraphOracleError(ValueError):
    """A reported graph or property vector is invalid."""


def normalize_graph(value: object) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    if not isinstance(value, Mapping):
        raise GraphOracleError("graph must be an object")
    vertices_value = value.get("vertices")
    edges_value = value.get("edges")
    if (
        not isinstance(vertices_value, Sequence)
        or isinstance(vertices_value, (str, bytes))
        or not all(isinstance(vertex, str) for vertex in vertices_value)
    ):
        raise GraphOracleError("graph vertices must be strings")
    vertices = tuple(vertices_value)
    if len(vertices) != len(set(vertices)):
        raise GraphOracleError("graph vertices must be unique")
    vertex_set = set(vertices)
    if not isinstance(edges_value, Sequence) or isinstance(edges_value, (str, bytes)):
        raise GraphOracleError("graph edges must be an array")
    edges: list[tuple[str, str]] = []
    for raw_edge in edges_value:
        if (
            not isinstance(raw_edge, Sequence)
            or isinstance(raw_edge, (str, bytes))
            or len(raw_edge) != 2
            or not all(isinstance(endpoint, str) for endpoint in raw_edge)
        ):
            raise GraphOracleError("each graph edge must contain two strings")
        source, target = raw_edge
        if source == target or source not in vertex_set or target not in vertex_set:
            raise GraphOracleError("graph edge violates simple-graph semantics")
        edges.append(tuple(sorted((source, target))))
    if len(edges) != len(set(edges)):
        raise GraphOracleError("graph edges must be unique")
    return vertices, tuple(sorted(edges))


def compute_properties(graph: object) -> dict[str, Any]:
    vertices, edges = normalize_graph(graph)
    adjacency: dict[str, set[str]] = {vertex: set() for vertex in vertices}
    for source, target in edges:
        adjacency[source].add(target)
        adjacency[target].add(source)
    degrees = [len(adjacency[vertex]) for vertex in vertices]
    connected = _is_connected(vertices, adjacency)
    bipartite = _is_bipartite(vertices, adjacency)
    triangles = sum(
        1
        for first, second, third in combinations(vertices, 3)
        if second in adjacency[first]
        and third in adjacency[first]
        and third in adjacency[second]
    )
    return {
        "order": len(vertices),
        "size": len(edges),
        "connected": connected,
        "bipartite": bipartite,
        "tree": connected and len(edges) == max(0, len(vertices) - 1),
        "triangle_count": triangles,
        "minimum_degree": min(degrees, default=0),
        "maximum_degree": max(degrees, default=0),
        "degree_sequence": sorted(degrees, reverse=True),
        "independence_number": _independence_number(vertices, adjacency),
    }


def check_constraints(properties: Mapping[str, Any], constraints: object) -> None:
    if not isinstance(constraints, Mapping):
        raise GraphOracleError("constraints must be an object")
    translations = {
        "triangle_free": ("triangle_count", 0),
        "minimum_edges": ("size", "minimum"),
        "maximum_edges": ("size", "maximum"),
    }
    for name, expected in constraints.items():
        if name == "triangle_free":
            if (properties["triangle_count"] == 0) != expected:
                raise GraphOracleError("graph violates triangle_free constraint")
        elif name in {"minimum_edges", "minimum_degree"}:
            property_name = translations.get(name, (name, "minimum"))[0]
            if properties[property_name] < expected:
                raise GraphOracleError(f"graph violates {name} constraint")
        elif name in {"maximum_edges", "maximum_degree"}:
            property_name = translations.get(name, (name, "maximum"))[0]
            if properties[property_name] > expected:
                raise GraphOracleError(f"graph violates {name} constraint")
        elif properties.get(name) != expected:
            raise GraphOracleError(f"graph violates {name} constraint")


def check_reported_properties(
    computed: Mapping[str, Any],
    reported: object,
    requested: object,
) -> None:
    if (
        not isinstance(reported, Mapping)
        or not isinstance(requested, Sequence)
        or isinstance(requested, (str, bytes))
    ):
        raise GraphOracleError("reported graph properties are malformed")
    expected_names = {str(name) for name in requested}
    unexpected_values = {
        name for name, value in reported.items() if name not in expected_names and value is not None
    }
    if not expected_names.issubset(reported) or unexpected_values:
        raise GraphOracleError("reported graph properties differ from requested set")
    for name in expected_names:
        value = reported[name]
        if isinstance(value, Mapping):
            if value.get("exactness") != "EXACT":
                raise GraphOracleError(f"graph property {name} is not exact")
            value = value.get("value")
        if value != computed[name]:
            raise GraphOracleError(f"graph property {name} differs from hidden oracle")


def _is_connected(
    vertices: tuple[str, ...],
    adjacency: Mapping[str, set[str]],
) -> bool:
    if not vertices:
        return False
    seen = {vertices[0]}
    pending = deque([vertices[0]])
    while pending:
        vertex = pending.popleft()
        for neighbor in adjacency[vertex]:
            if neighbor not in seen:
                seen.add(neighbor)
                pending.append(neighbor)
    return len(seen) == len(vertices)


def _is_bipartite(
    vertices: tuple[str, ...],
    adjacency: Mapping[str, set[str]],
) -> bool:
    colors: dict[str, int] = {}
    for start in vertices:
        if start in colors:
            continue
        colors[start] = 0
        pending = deque([start])
        while pending:
            vertex = pending.popleft()
            for neighbor in adjacency[vertex]:
                if neighbor not in colors:
                    colors[neighbor] = 1 - colors[vertex]
                    pending.append(neighbor)
                elif colors[neighbor] == colors[vertex]:
                    return False
    return True


def _independence_number(
    vertices: tuple[str, ...],
    adjacency: Mapping[str, set[str]],
) -> int:
    for size in range(len(vertices), -1, -1):
        for candidate in combinations(vertices, size):
            if all(second not in adjacency[first] for first, second in combinations(candidate, 2)):
                return size
    return 0
