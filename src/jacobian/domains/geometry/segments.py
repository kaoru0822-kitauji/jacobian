"""Segment-owned exact geometry capabilities."""

from jacobian.contracts.geometry import GeometryPointResult, PointPairRequest
from jacobian.domains.geometry._support import geometry_operation
from jacobian.domains.geometry.operations import midpoint

SEGMENT_CAPABILITIES = (
    geometry_operation(
        "geometry.segment.compute.midpoint",
        "Construct segment midpoint",
        "Construct the exact midpoint of two rational endpoints.",
        PointPairRequest,
        GeometryPointResult,
        midpoint,
        "geometry",
        "construction",
    ),
)
