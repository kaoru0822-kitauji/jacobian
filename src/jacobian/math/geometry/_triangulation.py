"""Exact bounded rational-weight triangulation of strict convex polygons."""

from __future__ import annotations

from fractions import Fraction

from jacobian._exact import CanonicalRational
from jacobian.canonical import format_canonical_integer
from jacobian.math.geometry._models import (
    ConvexPolygonTriangulationRequest,
    ConvexPolygonTriangulationResult,
    PolygonTriangle,
    TriangulationSplitEntry,
    WeightedPolygonDiagonal,
    _cross,
    _point_key,
    _reconstruct_split_triangulation,
    _require_bounded_split_table_rationals,
    _subtract,
    _triangulation_subproblem_costs,
)


def _wire(value: Fraction) -> CanonicalRational:
    return CanonicalRational(
        num=format_canonical_integer(value.numerator),
        den=format_canonical_integer(value.denominator),
    )


def minimum_weight_triangulation(
    request: ConvexPolygonTriangulationRequest,
) -> ConvexPolygonTriangulationResult:
    points = tuple(_point_key(point) for point in request.polygon.points)
    count = len(points)
    if not 4 <= count <= 32:
        raise ValueError("weighted triangulation supports 4 to 32 vertices")
    if any(
        _cross(
            _subtract(points[(index + 1) % count], points[index]),
            _subtract(points[(index + 2) % count], points[index]),
        )
        <= 0
        for index in range(count)
    ):
        raise ValueError("weighted triangulation requires strict CCW convexity")
    expected = {
        (first, second)
        for first in range(count)
        for second in range(first + 1, count)
        if second != first + 1 and (first, second) != (0, count - 1)
    }
    pairs = tuple((item.first, item.second) for item in request.diagonal_weights)
    if len(set(pairs)) != len(pairs) or set(pairs) != expected:
        raise ValueError("diagonal weights must cover every non-hull pair exactly")
    if pairs != tuple(sorted(pairs)):
        raise ValueError("diagonal weights must use lexicographic pair order")
    _require_bounded_split_table_rationals(count, request.diagonal_weights)
    weights = {
        (item.first, item.second): item.weight.as_fraction()
        for item in request.diagonal_weights
    }

    def edge_weight(first: int, second: int) -> Fraction:
        pair = (first, second) if first < second else (second, first)
        if second == first + 1 or pair == (0, count - 1):
            return Fraction()
        return weights[pair]

    optimum, split = _triangulation_subproblem_costs(count, edge_weight)
    ledger: list[TriangulationSplitEntry] = []
    for span in range(2, count):
        for start in range(count - span):
            end = start + span
            ledger.append(
                TriangulationSplitEntry(
                    start=start,
                    end=end,
                    split=split[start, end],
                    optimum=_wire(optimum[start, end]),
                )
            )

    diagonal_pairs, triangle_vertices = _reconstruct_split_triangulation(count, split)
    return ConvexPolygonTriangulationResult(
        vertex_count=count,
        diagonals=tuple(
            WeightedPolygonDiagonal(
                first=first, second=second, weight=_wire(weights[pair])
            )
            for pair in diagonal_pairs
            for first, second in (pair,)
        ),
        triangles=tuple(PolygonTriangle(vertices=item) for item in triangle_vertices),
        split_table=tuple(ledger),
        optimum=_wire(optimum[0, count - 1]),
    )


__all__ = ["minimum_weight_triangulation"]
