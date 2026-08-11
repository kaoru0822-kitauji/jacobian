"""Typed requests for atomic finite-field operations."""

from jacobian.contracts.base import ContractModel
from jacobian.math.finite_fields import (
    FiniteDimensionalSubspace,
    FiniteLinearMap,
    ProjectivePoint,
)


class RestrictScalarsRequest(ContractModel):
    subspace: FiniteDimensionalSubspace
    direction: ProjectivePoint


class LinearMapRankRequest(ContractModel):
    direction: ProjectivePoint
    linear_map: FiniteLinearMap


__all__ = ["LinearMapRankRequest", "RestrictScalarsRequest"]
