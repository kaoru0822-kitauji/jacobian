"""Line-owned exact geometry capabilities."""

from jacobian.contracts.geometry import (
    GeometryBooleanResult,
    GeometryLineIntersectionResult,
    GeometryPointResult,
    LinePairRequest,
    PointLineRequest,
)
from jacobian.domains.geometry._support import geometry_operation
from jacobian.domains.geometry.operations import (
    line_intersection,
    line_predicate,
    projection,
)

LINE_CAPABILITIES = (
    geometry_operation(
        "geometry.lines.decide.parallel",
        "Decide parallel lines",
        "Decide whether two exact lines are parallel.",
        LinePairRequest,
        GeometryBooleanResult,
        line_predicate(lambda first, second: bool(first.is_parallel(second))),
        "geometry",
        "line",
    ),
    geometry_operation(
        "geometry.lines.decide.perpendicular",
        "Decide perpendicular lines",
        "Decide whether two exact lines are perpendicular.",
        LinePairRequest,
        GeometryBooleanResult,
        line_predicate(lambda first, second: bool(first.is_perpendicular(second))),
        "geometry",
        "line",
    ),
    geometry_operation(
        "geometry.lines.compute.intersection",
        "Intersect exact lines",
        "Return the exact point, parallel status, or coincident status for two lines.",
        LinePairRequest,
        GeometryLineIntersectionResult,
        line_intersection,
        "geometry",
        "intersection",
    ),
    geometry_operation(
        "geometry.line.compute.projection",
        "Project point onto line",
        "Construct the exact orthogonal projection of a rational point onto a line.",
        PointLineRequest,
        GeometryPointResult,
        projection,
        "geometry",
        "construction",
    ),
)
