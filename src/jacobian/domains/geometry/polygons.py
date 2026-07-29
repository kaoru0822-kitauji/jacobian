"""Polygon-owned exact geometry capabilities."""

from jacobian.contracts.geometry import GeometryRationalResult, PolygonRequest
from jacobian.domains._examples import example
from jacobian.domains.geometry._support import geometry_operation
from jacobian.domains.geometry.operations import signed_area

POLYGON_CAPABILITIES = (
    geometry_operation(
        "geometry.polygon.compute.signed_area",
        "Compute polygon signed area",
        "Compute exact oriented area of a simple rational polygon.",
        PolygonRequest,
        GeometryRationalResult,
        signed_area,
        "geometry",
        "polygon",
        invocation_examples=(
            example(
                "unit_square_signed_area",
                "Compute the signed area of a unit square.",
                {
                    "points": [
                        {"x": {"num": "0", "den": "1"}, "y": {"num": "0", "den": "1"}},
                        {"x": {"num": "1", "den": "1"}, "y": {"num": "0", "den": "1"}},
                        {"x": {"num": "1", "den": "1"}, "y": {"num": "1", "den": "1"}},
                        {"x": {"num": "0", "den": "1"}, "y": {"num": "1", "den": "1"}},
                    ]
                },
            ),
        ),
    ),
)
