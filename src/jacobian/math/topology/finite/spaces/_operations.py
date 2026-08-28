"""Domain adapter for finite topological space operations."""

from __future__ import annotations

from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.topology.finite.spaces._models import (
    BoundaryResult,
    ClosureResult,
    ContinuousCheckRequest,
    ContinuousCheckResult,
    InteriorResult,
    KolmogorovQuotientRequest,
    KolmogorovQuotientResult,
    SubsetRequest,
)
from jacobian.math.topology.finite.spaces.operations import (
    boundary,
    closure,
    continuous_check,
    interior,
    kolmogorov_quotient,
)

__all__ = [
    "compute_boundary",
    "compute_closure",
    "compute_continuous_check",
    "compute_interior",
    "compute_kolmogorov_quotient",
]


def _admit_subset(request: SubsetRequest) -> frozenset[int]:
    if any(not 0 <= index < len(request.space.points) for index in request.subset):
        raise OperationDomainValidationError(
            location=("subset",),
            code="finite_topology_space.subset_index_out_of_range",
            message="subset index out of range",
        )
    return frozenset(request.subset)


def compute_interior(request: SubsetRequest) -> InteriorResult:
    result = interior(request.space, _admit_subset(request))
    return InteriorResult(interior=tuple(sorted(result)))


def compute_closure(request: SubsetRequest) -> ClosureResult:
    result = closure(request.space, _admit_subset(request))
    return ClosureResult(closure=tuple(sorted(result)))


def compute_boundary(request: SubsetRequest) -> BoundaryResult:
    result = boundary(request.space, _admit_subset(request))
    return BoundaryResult(boundary=tuple(sorted(result)))


def compute_continuous_check(
    request: ContinuousCheckRequest,
) -> ContinuousCheckResult:
    result = continuous_check(request.point_map)
    return ContinuousCheckResult(is_continuous=result)


def compute_kolmogorov_quotient(
    request: KolmogorovQuotientRequest,
) -> KolmogorovQuotientResult:
    return kolmogorov_quotient(request.space)
