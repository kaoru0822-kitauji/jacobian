"""Exact rational planar-geometry operations."""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction
from typing import Any, cast

from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.geometry import (
    GeometryBooleanResult,
    GeometryCircleResult,
    GeometryLineIntersectionResult,
    GeometryOrientationResult,
    GeometryPointResult,
    GeometryPointSetResult,
    GeometryRationalResult,
    LinePairRequest,
    LineRequest,
    PointLineRequest,
    PointPairRequest,
    PointQuadrupleRequest,
    PointSetRequest,
    PointTripleRequest,
    PolygonRequest,
    RationalPoint2D,
)
from jacobian.contracts.results import ContractModel

Compute = Callable[[ContractModel], ContractModel]


def _fraction(value: Any) -> Fraction:
    import sympy

    rational = sympy.Rational(value)
    return Fraction(int(rational.p), int(rational.q))


def _wire_rational(value: Any) -> CanonicalRational:
    fraction = _fraction(value)
    return CanonicalRational(
        num=str(fraction.numerator),
        den=str(fraction.denominator),
    )


def _point(value: RationalPoint2D) -> Any:
    import sympy
    from sympy.geometry import Point2D

    return Point2D(
        sympy.Rational(int(value.x.num), int(value.x.den)),
        sympy.Rational(int(value.y.num), int(value.y.den)),
    )


def _wire_point(value: Any) -> RationalPoint2D:
    return RationalPoint2D(
        x=_wire_rational(value.x),
        y=_wire_rational(value.y),
    )


def _pair_points(request: ContractModel) -> tuple[Any, Any]:
    pair = cast(PointPairRequest, request)
    return _point(pair.first), _point(pair.second)


def _line(value: LineRequest) -> Any:
    from sympy.geometry import Line2D

    return Line2D(_point(value.first), _point(value.second))


def squared_distance(request: ContractModel) -> ContractModel:
    first, second = _pair_points(request)
    return GeometryRationalResult(value=_wire_rational(first.distance(second) ** 2))


def midpoint(request: ContractModel) -> ContractModel:
    first, second = _pair_points(request)
    return GeometryPointResult(point=_wire_point(first.midpoint(second)))


def collinear(request: ContractModel) -> ContractModel:
    from sympy.geometry import Point2D

    triple = cast(PointTripleRequest, request)
    return GeometryBooleanResult(
        holds=Point2D.is_collinear(
            _point(triple.first),
            _point(triple.second),
            _point(triple.third),
        )
    )


def concyclic(request: ContractModel) -> ContractModel:
    from sympy.geometry import Point2D

    points = cast(PointQuadrupleRequest, request)
    return GeometryBooleanResult(
        holds=Point2D.is_concyclic(
            _point(points.first),
            _point(points.second),
            _point(points.third),
            _point(points.fourth),
        )
    )


def line_predicate(
    predicate: Callable[[Any, Any], bool],
) -> Compute:
    def compute(request: ContractModel) -> ContractModel:
        pair = cast(LinePairRequest, request)
        return GeometryBooleanResult(
            holds=predicate(_line(pair.first_line), _line(pair.second_line))
        )

    return compute


def line_intersection(request: ContractModel) -> ContractModel:
    from sympy.geometry import Point2D

    pair = cast(LinePairRequest, request)
    first, second = _line(pair.first_line), _line(pair.second_line)
    if first.equals(second):
        return GeometryLineIntersectionResult(status="COINCIDENT")
    intersections = first.intersection(second)
    if not intersections:
        return GeometryLineIntersectionResult(status="PARALLEL")
    point = intersections[0]
    if not isinstance(point, Point2D):
        raise ValueError("line intersection did not produce one exact point")
    return GeometryLineIntersectionResult(status="POINT", point=_wire_point(point))


def projection(request: ContractModel) -> ContractModel:
    from sympy.geometry import Point2D

    value = cast(PointLineRequest, request)
    projected = _line(value.line).projection(_point(value.point))
    if not isinstance(projected, Point2D):
        raise ValueError("line projection did not produce one exact point")
    return GeometryPointResult(point=_wire_point(projected))


def orientation(request: ContractModel) -> ContractModel:
    import sympy

    triple = cast(PointTripleRequest, request)
    first, second, third = (
        _point(triple.first),
        _point(triple.second),
        _point(triple.third),
    )
    determinant = (second.x - first.x) * (third.y - first.y) - (second.y - first.y) * (
        third.x - first.x
    )
    return GeometryOrientationResult(
        orientation=cast(Any, int(sympy.sign(determinant)))
    )


def centroid(request: ContractModel) -> ContractModel:
    from sympy.geometry import Point2D

    triple = cast(PointTripleRequest, request)
    points = [_point(triple.first), _point(triple.second), _point(triple.third)]
    return GeometryPointResult(
        point=_wire_point(
            Point2D(
                sum(point.x for point in points) / 3,
                sum(point.y for point in points) / 3,
            )
        )
    )


def circumcircle(request: ContractModel) -> ContractModel:
    from sympy.geometry import Circle, Point2D

    triple = cast(PointTripleRequest, request)
    points = [_point(triple.first), _point(triple.second), _point(triple.third)]
    if Point2D.is_collinear(*points):
        raise ValueError("a circumcircle requires three noncollinear points")
    circle = Circle(*points)
    return GeometryCircleResult(
        center=_wire_point(circle.center),
        radius_squared=_wire_rational(circle.radius**2),
    )


def signed_area(request: ContractModel) -> ContractModel:
    from sympy.geometry import Polygon

    polygon = cast(PolygonRequest, request)
    value = Polygon(*(_point(point) for point in polygon.points)).area
    return GeometryRationalResult(value=_wire_rational(value))


def convex_hull_points(request: ContractModel) -> ContractModel:
    from sympy.geometry import Line2D, Point2D, Polygon, Segment2D
    from sympy.geometry.util import convex_hull

    point_set = cast(PointSetRequest, request)
    hull = convex_hull(*(_point(point) for point in point_set.points))
    if isinstance(hull, Point2D):
        points = (hull,)
    elif isinstance(hull, (Line2D, Segment2D)):
        points = tuple(
            sorted(
                cast(tuple[Point2D, Point2D], hull.points),
                key=lambda point: (point.x, point.y),
            )
        )
    else:
        points = tuple(cast(Polygon, hull).vertices)
    return GeometryPointSetResult(points=tuple(_wire_point(point) for point in points))
