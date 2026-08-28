"""Typed contracts for divisibility-incidence graph construction."""

from __future__ import annotations

from pydantic import Field

from jacobian._models import StrictModel
from jacobian.math.graphs.values import SimpleUndirectedGraph
from jacobian.math.number_theory._models import BoundedInteger

MAX_FAMILY_SIZE: int = 256
MAX_TOTAL_FAMILY_SIZE: int = 256
MAX_GRAPH_EDGES: int = 32_640


class DivisibilityIncidenceGraphRequest(StrictModel):
    """Two finite positive-integer families whose divisibility incidence graph is constructed."""

    left_family: tuple[BoundedInteger, ...] = Field(
        max_length=MAX_FAMILY_SIZE,
        description="Unique positive integers labelling the left vertex family.",
    )
    right_family: tuple[BoundedInteger, ...] = Field(
        max_length=MAX_FAMILY_SIZE,
        description="Unique positive integers labelling the right vertex family.",
    )


class DivisibilityIncidenceGraphResult(StrictModel):
    """Canonical bipartite simple graph with edges for each (l, r) with l | r."""

    left_family: tuple[BoundedInteger, ...]
    right_family: tuple[BoundedInteger, ...]
    graph: SimpleUndirectedGraph


__all__ = [
    "MAX_FAMILY_SIZE",
    "MAX_GRAPH_EDGES",
    "MAX_TOTAL_FAMILY_SIZE",
    "DivisibilityIncidenceGraphRequest",
    "DivisibilityIncidenceGraphResult",
]
