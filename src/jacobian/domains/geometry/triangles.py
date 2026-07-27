"""Triangle-owned exact geometry capabilities."""

from jacobian.contracts.geometry import (
    GeometryCircleResult,
    GeometryOrientationResult,
    GeometryPointResult,
    PointTripleRequest,
)
from jacobian.domains.geometry._support import geometry_operation
from jacobian.domains.geometry.operations import centroid, circumcircle, orientation

TRIANGLE_CAPABILITIES = (
    geometry_operation(
        "geometry.triangle.compute.orientation",
        "Compute triangle orientation",
        "Return clockwise, collinear, or counterclockwise orientation as -1, 0, or 1.",
        PointTripleRequest,
        GeometryOrientationResult,
        orientation,
        "geometry",
        "orientation",
    ),
    geometry_operation(
        "geometry.triangle.compute.centroid",
        "Construct triangle centroid",
        "Construct the exact centroid of three rational points.",
        PointTripleRequest,
        GeometryPointResult,
        centroid,
        "geometry",
        "construction",
    ),
    geometry_operation(
        "geometry.triangle.compute.circumcircle",
        "Construct triangle circumcircle",
        "Construct the exact circumcenter and squared radius of a nondegenerate rational triangle.",
        PointTripleRequest,
        GeometryCircleResult,
        circumcircle,
        "geometry",
        "circle",
    ),
)
