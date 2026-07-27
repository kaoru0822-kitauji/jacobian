"""Polygon-owned exact geometry capabilities."""

from jacobian.contracts.geometry import GeometryRationalResult, PolygonRequest
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
    ),
)
