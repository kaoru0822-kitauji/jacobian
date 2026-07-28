"""Point-owned exact geometry capabilities."""

from jacobian.contracts.geometry import (
    GeometryBooleanResult,
    GeometryPointSetResult,
    GeometryRationalResult,
    PointPairRequest,
    PointQuadrupleRequest,
    PointSetRequest,
    PointTripleRequest,
)
from jacobian.domains._examples import example
from jacobian.domains.geometry._support import geometry_operation
from jacobian.domains.geometry.operations import (
    collinear,
    concyclic,
    convex_hull_points,
    squared_distance,
)

POINT_CAPABILITIES = (
    geometry_operation(
        "geometry.points.compute.squared_distance",
        "Compute squared distance",
        "Compute exact squared Euclidean distance between two rational points.",
        PointPairRequest,
        GeometryRationalResult,
        squared_distance,
        "geometry",
        "distance",
        invocation_examples=(example("diagonal_squared_distance", "Compute the squared distance from (0,0) to (2,2).", {"first": {"x": {"num": "0", "den": "1"}, "y": {"num": "0", "den": "1"}}, "second": {"x": {"num": "2", "den": "1"}, "y": {"num": "2", "den": "1"}}}),),
    ),
    geometry_operation(
        "geometry.points.decide.collinear",
        "Decide collinearity",
        "Decide exact collinearity of three rational points.",
        PointTripleRequest,
        GeometryBooleanResult,
        collinear,
        "geometry",
        "incidence",
    ),
    geometry_operation(
        "geometry.points.decide.concyclic",
        "Decide concyclicity",
        "Decide whether four rational points lie on one circle.",
        PointQuadrupleRequest,
        GeometryBooleanResult,
        concyclic,
        "geometry",
        "circle",
    ),
    geometry_operation(
        "geometry.points.compute.convex_hull",
        "Construct planar convex hull",
        "Construct the exact convex hull vertices of a finite rational point set.",
        PointSetRequest,
        GeometryPointSetResult,
        convex_hull_points,
        "geometry",
        "convexity",
        invocation_examples=(example("square_convex_hull", "Construct the hull of a rational square.", {"points": [{"x": {"num": "0", "den": "1"}, "y": {"num": "0", "den": "1"}}, {"x": {"num": "2", "den": "1"}, "y": {"num": "0", "den": "1"}}, {"x": {"num": "0", "den": "1"}, "y": {"num": "2", "den": "1"}}, {"x": {"num": "2", "den": "1"}, "y": {"num": "2", "den": "1"}}]}),),
    ),
)
