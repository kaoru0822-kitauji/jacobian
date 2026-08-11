"""Typed requests for atomic finite-field operations."""

from jacobian.contracts.base import ContractModel
from jacobian.math.finite_fields import (
    Axis,
    DirectionRankLedger,
    FiniteDimensionalSubspace,
    FiniteFieldPresentation,
    FiniteLinearMap,
    ProjectiveLine,
    ProjectivePoint,
)


class RestrictScalarsRequest(ContractModel):
    subspace: FiniteDimensionalSubspace
    direction: ProjectivePoint


class LinearMapRankRequest(ContractModel):
    direction: ProjectivePoint
    linear_map: FiniteLinearMap


class ProjectiveLineRequest(ContractModel):
    presentation: FiniteFieldPresentation
    axis: Axis


class DirectionRankLedgerRequest(ContractModel):
    subspace: FiniteDimensionalSubspace
    directions: ProjectiveLine


class OrbitDistributionRequest(ContractModel):
    ledger: DirectionRankLedger


__all__ = [
    "DirectionRankLedgerRequest",
    "LinearMapRankRequest",
    "OrbitDistributionRequest",
    "ProjectiveLineRequest",
    "RestrictScalarsRequest",
]
