"""Deterministic algorithms on NetworkX undirected simple graphs."""

from __future__ import annotations

from typing import Any, cast

import networkx as nx

__all__ = ["diameter", "is_eulerian", "triangle_count"]


def _simple_graph(graph: nx.Graph[Any]) -> nx.Graph[Any]:
    if not isinstance(graph, nx.Graph):
        raise TypeError("graph must be a NetworkX Graph")
    if graph.is_directed() or graph.is_multigraph():
        raise ValueError("graph must be undirected and simple")
    if graph.number_of_nodes() > 32:
        raise ValueError("graph may contain at most 32 vertices")
    if nx.number_of_selfloops(graph):
        raise ValueError("graph must not contain self-loops")
    return graph


def triangle_count(graph: nx.Graph[Any]) -> int:
    """Count the triangles in an undirected simple graph."""

    counts = cast(dict[Any, int], nx.triangles(_simple_graph(graph)))
    return sum(counts.values()) // 3


def diameter(graph: nx.Graph[Any]) -> int:
    """Return graph diameter, requiring a nonempty connected graph."""

    value = _simple_graph(graph)
    if not value or not nx.is_connected(value):
        raise ValueError("diameter requires a nonempty connected graph")
    return int(nx.diameter(value))


def is_eulerian(graph: nx.Graph[Any]) -> bool:
    """Return whether the graph has an Eulerian circuit."""

    return bool(nx.is_eulerian(_simple_graph(graph)))
