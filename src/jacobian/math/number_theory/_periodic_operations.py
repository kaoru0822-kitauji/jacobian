"""Exact finite congruence-union operations."""

from __future__ import annotations

from fractions import Fraction

from jacobian._exact import CanonicalRational
from jacobian.canonical import format_canonical_integer, parse_canonical_integer
from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.number_theory._periodic_kernel import (
    _ExecutionPlan,
    materialize_periodic_union,
    measure_periodic_union,
    require_admitted_periodic_source,
    require_materializable_periodic_source,
)
from jacobian.math.number_theory._periodic_models import (
    PeriodicCongruenceSubset,
    PeriodicCongruenceUnionMeasureResult,
    PeriodicCongruenceUnionProfileRequest,
    PeriodicCongruenceUnionProfileResult,
    PeriodicCongruenceUnionRequest,
    PeriodicCongruenceUnionSource,
)


def normalize_periodic_source(
    request: PeriodicCongruenceUnionRequest,
) -> PeriodicCongruenceUnionSource:
    """Normalize request rows into the canonical source consumed by kernels."""

    merged: dict[int, set[int]] = {}
    for subset in request.subsets:
        modulus = parse_canonical_integer(subset.modulus)
        residues = merged.setdefault(modulus, set())
        residues.update(
            parse_canonical_integer(residue) % modulus for residue in subset.residues
        )
    return PeriodicCongruenceUnionSource(
        subsets=tuple(
            PeriodicCongruenceSubset(
                modulus=format_canonical_integer(modulus),
                residues=tuple(
                    format_canonical_integer(residue) for residue in sorted(residues)
                ),
            )
            for modulus, residues in sorted(merged.items())
        ),
        complement=request.complement,
    )


def _admit_source(
    source: PeriodicCongruenceUnionSource, *, materializable: bool = False
) -> _ExecutionPlan:
    try:
        if materializable:
            return require_materializable_periodic_source(source)
        return require_admitted_periodic_source(source)
    except ValueError as exc:
        raise OperationDomainValidationError(
            location=("subsets",),
            code="number_theory.periodic.execution_bound",
            message=str(exc),
        ) from exc


def _measure_values(
    period: int,
    occupied_count: int,
) -> tuple[str, str, CanonicalRational]:
    return (
        format_canonical_integer(period),
        format_canonical_integer(occupied_count),
        CanonicalRational.from_fraction(Fraction(occupied_count, period)),
    )


def compute_periodic_congruence_union_measure(
    request: PeriodicCongruenceUnionRequest,
) -> PeriodicCongruenceUnionMeasureResult:
    """Compute the exact count and density of a finite congruence union."""

    source = normalize_periodic_source(request)
    plan = _admit_source(source)
    period, occupied_count, density = _measure_values(
        plan.common_period, measure_periodic_union(source, plan)
    )
    return PeriodicCongruenceUnionMeasureResult._from_kernel(
        source=source,
        common_period=period,
        occupied_count=occupied_count,
        density=density,
    )


def compute_periodic_congruence_union_profile(
    request: PeriodicCongruenceUnionProfileRequest,
) -> PeriodicCongruenceUnionProfileResult:
    """Materialize the complete common-period residue profile."""

    source = normalize_periodic_source(request)
    plan = _admit_source(source, materializable=True)
    residues = materialize_periodic_union(source, plan)
    period, occupied_count, density = _measure_values(plan.common_period, len(residues))
    return PeriodicCongruenceUnionProfileResult._from_profile_kernel(
        source=source,
        common_period=period,
        occupied_count=occupied_count,
        density=density,
        occupied_residues=tuple(
            format_canonical_integer(residue) for residue in residues
        ),
    )


__all__ = [
    "compute_periodic_congruence_union_measure",
    "compute_periodic_congruence_union_profile",
    "normalize_periodic_source",
]
