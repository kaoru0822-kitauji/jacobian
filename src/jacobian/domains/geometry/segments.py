"""Segment-owned exact geometry capabilities."""

from jacobian.contracts.geometry import GeometryPointResult, PointPairRequest
from jacobian.domains._examples import example
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
        invocation_examples=(example("segment_midpoint", "Construct the midpoint of a unit segment.", {"first": {"x": {"num": "0", "den": "1"}, "y": {"num": "0", "den": "1"}}, "second": {"x": {"num": "1", "den": "1"}, "y": {"num": "0", "den": "1"}}}),),
    ),
)
