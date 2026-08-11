"""Typed requests for atomic finite-field operations."""

from jacobian.contracts.base import ContractModel
from jacobian.math.finite_fields import (
    Axis,
    DirectionRankLedger,
    FiniteDimensionalSubspace,
    FiniteFieldPresentation,
    FiniteLinearMap,
    FiniteMapTable,
    FinitePolynomialMap,
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


class FiniteMapTableRequest(ContractModel):
    polynomial_map: FinitePolynomialMap


class FiberPartitionRequest(ContractModel):
    table: FiniteMapTable


class CollisionCertificateRequest(ContractModel):
    table: FiniteMapTable


class PermutationCertificateRequest(ContractModel):
    table: FiniteMapTable


__all__ = [
    "CollisionCertificateRequest",
    "DirectionRankLedgerRequest",
    "FiberPartitionRequest",
    "FiniteMapTableRequest",
    "LinearMapRankRequest",
    "OrbitDistributionRequest",
    "PermutationCertificateRequest",
    "ProjectiveLineRequest",
    "RestrictScalarsRequest",
]
