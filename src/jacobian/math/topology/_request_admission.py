"""Request-time admission for finite simplicial topology operations."""

from __future__ import annotations

from jacobian.math.topology._models import (
    MAX_TOPOLOGY_DIMENSION,
    SimplicialComplexRequest,
    _require_request_complex,
)


def require_complex_admission(request: SimplicialComplexRequest) -> None:
    """Check semantic complex bounds immediately before a kernel runs."""
    if any(
        not 1 <= len(facet) <= MAX_TOPOLOGY_DIMENSION + 1
        for facet in request.facets
    ):
        raise ValueError(
            "each facet must contain between 1 and "
            f"{MAX_TOPOLOGY_DIMENSION + 1} vertices"
        )
    _require_request_complex(request.vertices, request.facets)


__all__ = ["require_complex_admission"]
