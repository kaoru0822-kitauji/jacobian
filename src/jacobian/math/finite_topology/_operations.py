"""Wire adapters for public finite-topology operations."""

from __future__ import annotations

from jacobian.math.finite_topology._models import (
    BeatPointsRequest,
    BeatPointsResult,
    ConnectedComponentsRequest,
    ConnectedComponentsResult,
    ContinuityRequest,
    ContinuityResult,
    SpecializationPreorderRequest,
    SpecializationPreorderResult,
)
from jacobian.math.finite_topology.operations import (
    beat_points,
    connected_components,
    continuity,
    specialization_preorder,
)


def compute_specialization_preorder(
    request: SpecializationPreorderRequest,
) -> SpecializationPreorderResult:
    return SpecializationPreorderResult._from_kernel(
        request, specialization_preorder(request.topology)
    )


def compute_connected_components(
    request: ConnectedComponentsRequest,
) -> ConnectedComponentsResult:
    components = connected_components(request.topology)
    return ConnectedComponentsResult._from_kernel(request, components)


def compute_continuity(request: ContinuityRequest) -> ContinuityResult:
    analysis = continuity(request.domain, request.codomain, request.point_map)
    return ContinuityResult._from_kernel(
        request,
        is_continuous=analysis.is_continuous,
        violating_open_set=analysis.violating_open_set,
        violating_preimage=analysis.violating_preimage,
    )


def compute_beat_points(request: BeatPointsRequest) -> BeatPointsResult:
    analysis = beat_points(request.topology)
    return BeatPointsResult._from_kernel(
        request,
        down_beat_points=analysis.down_beat_points,
        up_beat_points=analysis.up_beat_points,
    )


__all__ = [
    "compute_beat_points",
    "compute_connected_components",
    "compute_continuity",
    "compute_specialization_preorder",
]
