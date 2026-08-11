"""Exact operations on presentation-, parent-, and axis-bound finite-field values."""

from __future__ import annotations

from jacobian.math.finite_fields.values import (
    Axis,
    DirectionRankLedger,
    FiniteDimensionalSubspace,
    FiniteFieldElement,
    FiniteFieldPresentation,
    FiniteLinearMap,
    OrbitDistribution,
    ProjectivePoint,
    RankResult,
)
from jacobian.math.prime_field_linear_algebra import PrimeFieldMatrix


def finite_field(
    characteristic: int,
    modulus_coefficients: tuple[int, ...],
    *,
    generator: str = "a",
) -> FiniteFieldPresentation:
    """Construct and backend-check an exact finite-extension presentation."""

    presentation = FiniteFieldPresentation(
        characteristic=characteristic,
        modulus_coefficients=modulus_coefficients,
        generator=generator,
    )
    from jacobian.math.finite_fields import _flint

    _flint.context(presentation)
    return presentation


def element(
    presentation: FiniteFieldPresentation,
    coordinates: tuple[int, ...],
) -> FiniteFieldElement:
    """Construct one parent-bound element from canonical power-basis coordinates."""

    return FiniteFieldElement(presentation=presentation, coordinates=coordinates)


def projective_point(
    presentation: FiniteFieldPresentation,
    axis: Axis,
    coordinates: tuple[FiniteFieldElement, ...],
) -> ProjectivePoint:
    """Normalize nonzero homogeneous coordinates by their first nonzero entry."""

    if len(coordinates) != len(axis.labels):
        raise ValueError("projective coordinates must match their axis")
    if any(value.presentation != presentation for value in coordinates):
        raise ValueError("projective coordinates must share their presentation")
    from jacobian.math.finite_fields import _flint

    active_context = _flint.context(presentation)
    backend_values = tuple(
        _flint.to_backend(value, active_context=active_context) for value in coordinates
    )
    backend_zero = active_context(0)
    pivot = next((value for value in backend_values if value != backend_zero), None)
    if pivot is None:
        raise ValueError("projective coordinates cannot all be zero")
    normalized = tuple(value / pivot for value in backend_values)
    return ProjectivePoint(
        presentation=presentation,
        axis=axis,
        coordinates=tuple(
            FiniteFieldElement(
                presentation=presentation,
                coordinates=_flint.coordinates(value, degree=presentation.degree),
            )
            for value in normalized
        ),
    )


def projective_line(
    presentation: FiniteFieldPresentation,
    axis: Axis,
) -> tuple[ProjectivePoint, ...]:
    """Enumerate a projective line in deterministic power-basis encoding order."""

    if len(axis.labels) != 2:
        raise ValueError("projective-line enumeration requires a two-coordinate axis")
    zero = element(presentation, (0,) * presentation.degree)
    one = element(presentation, (1,) + (0,) * (presentation.degree - 1))
    affine_elements = tuple(
        element(
            presentation,
            tuple(
                (encoded // presentation.characteristic**power)
                % presentation.characteristic
                for power in range(presentation.degree)
            ),
        )
        for encoded in range(presentation.order)
    )
    return (
        projective_point(presentation, axis, (zero, one)),
        *(
            projective_point(presentation, axis, (one, value))
            for value in affine_elements
        ),
    )


def restrict_scalars(
    subspace: FiniteDimensionalSubspace,
    direction: ProjectivePoint,
) -> FiniteLinearMap:
    """Construct ``B -> B^T b`` over the exact prime-field coordinate basis."""

    if direction.presentation != subspace.presentation:
        raise ValueError("direction and subspace must share their field presentation")
    if direction.axis != subspace.row_axis:
        raise ValueError("direction axis must match the subspace matrix row axis")
    from jacobian.math.finite_fields import _flint

    active_context = _flint.context(subspace.presentation)
    backend_direction = tuple(
        _flint.to_backend(value, active_context=active_context)
        for value in direction.coordinates
    )
    columns: list[tuple[int, ...]] = []
    for matrix in subspace.basis:
        backend_matrix = tuple(
            tuple(
                _flint.to_backend(value, active_context=active_context) for value in row
            )
            for row in matrix.entries
        )
        image = tuple(
            sum(
                (
                    backend_matrix[row][column] * backend_direction[row]
                    for row in range(len(matrix.row_axis.labels))
                ),
                active_context(0),
            )
            for column in range(len(matrix.column_axis.labels))
        )
        columns.append(
            tuple(
                coordinate
                for value in image
                for coordinate in _flint.coordinates(
                    value,
                    degree=subspace.presentation.degree,
                )
            )
        )
    target_axis = Axis(
        name=f"Res({subspace.column_axis.name})",
        labels=tuple(
            f"{label}:{basis}"
            for label in subspace.column_axis.labels
            for basis in subspace.presentation.ordered_basis
        ),
    )
    return FiniteLinearMap(
        source_axis=subspace.basis_axis,
        target_axis=target_axis,
        matrix=PrimeFieldMatrix(
            prime=subspace.presentation.characteristic,
            entries=tuple(zip(*columns, strict=True)),
            columns=len(subspace.basis),
        ),
    )


def linear_map_rank(
    direction: ProjectivePoint,
    linear_map: FiniteLinearMap,
) -> RankResult:
    """Compute FLINT rank while retaining the exact direction and map."""

    from jacobian.math.finite_fields import _flint

    return RankResult(
        direction=direction,
        linear_map=linear_map,
        rank=_flint.matrix_rank(linear_map.matrix),
    )


def direction_rank_ledger(
    subspace: FiniteDimensionalSubspace,
    directions: tuple[ProjectivePoint, ...],
) -> DirectionRankLedger:
    """Restrict scalars and rank every supplied direction without losing order."""

    return DirectionRankLedger(
        subspace=subspace,
        entries=tuple(
            linear_map_rank(direction, restrict_scalars(subspace, direction))
            for direction in directions
        ),
    )


def orbit_distribution(ledger: DirectionRankLedger) -> OrbitDistribution:
    """Aggregate projective orbit counts from a complete direction-rank ledger."""

    return OrbitDistribution.from_ledger(ledger)
