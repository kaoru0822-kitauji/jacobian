"""Process-local immutable access to NetworkX Graph Atlas representatives."""

from __future__ import annotations

from functools import cache
from typing import Any

import networkx as nx

_MAX_ATLAS_ORDER = 7


@cache
def _graph_atlas_by_order() -> tuple[tuple[nx.Graph[Any], ...], ...]:
    grouped: list[list[nx.Graph[Any]]] = [[] for _ in range(_MAX_ATLAS_ORDER + 1)]
    for graph in nx.graph_atlas_g():
        grouped[graph.number_of_nodes()].append(nx.freeze(graph))
    return tuple(tuple(graphs) for graphs in grouped)


def graph_atlas_order(order: int) -> tuple[nx.Graph[Any], ...]:
    """Return frozen atlas representatives of one supported order."""

    if not 0 <= order <= _MAX_ATLAS_ORDER:
        raise ValueError("Graph Atlas order must be between zero and seven")
    return _graph_atlas_by_order()[order]
