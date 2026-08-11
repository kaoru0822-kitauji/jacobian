from __future__ import annotations

import pytest

from jacobian.math.finite_fields import (
    Axis,
    AxisBoundMatrix,
    FiniteDimensionalSubspace,
    FiniteFieldElement,
    FiniteFieldPresentation,
    FiniteLinearMap,
    ProjectivePoint,
    RankResult,
)
from jacobian.math.prime_field_linear_algebra import PrimeFieldMatrix


def _presentation(*, generator: str = "a") -> FiniteFieldPresentation:
    return FiniteFieldPresentation(
        characteristic=2,
        modulus_coefficients=(1, 1, 0, 1),
        generator=generator,
    )


def _element(
    presentation: FiniteFieldPresentation,
    coordinates: tuple[int, int, int],
) -> FiniteFieldElement:
    return FiniteFieldElement(presentation, coordinates)


def test_presentation_identity_binds_modulus_generator_basis_and_encoding() -> None:
    presentation = _presentation()

    assert presentation.degree == 3
    assert presentation.order == 8
    assert presentation.ordered_basis == ("1", "a", "a^2")
    assert presentation.digest == _presentation().digest
    assert presentation.digest != _presentation(generator="z").digest


def test_presentation_rejects_reducible_or_noncanonical_moduli() -> None:
    with pytest.raises(ValueError, match="irreducible"):
        FiniteFieldPresentation(2, (0, 0, 1))
    with pytest.raises(ValueError, match="canonical"):
        FiniteFieldPresentation(2, (1, 3, 1))


def test_values_reject_same_shape_substitutions_with_wrong_parent_or_axis() -> None:
    presentation = _presentation()
    other_presentation = _presentation(generator="z")
    row_axis = Axis("rows", ("r1", "r2"))
    column_axis = Axis("columns", ("c1", "c2"))
    wrong_axis = Axis("other rows", ("r1", "r2"))
    zero = _element(presentation, (0, 0, 0))
    one = _element(presentation, (1, 0, 0))

    with pytest.raises(ValueError, match="presentation"):
        AxisBoundMatrix(
            presentation,
            row_axis,
            column_axis,
            ((one, zero), (zero, _element(other_presentation, (1, 0, 0)))),
        )
    with pytest.raises(ValueError, match="normalized"):
        ProjectivePoint(
            presentation,
            row_axis,
            (_element(presentation, (0, 1, 0)), zero),
        )
    matrix = FiniteLinearMap(
        source_axis=column_axis,
        target_axis=row_axis,
        matrix=PrimeFieldMatrix(2, ((1, 0), (0, 1)), 2),
    )
    with pytest.raises(ValueError, match="target axis"):
        FiniteLinearMap(
            source_axis=column_axis,
            target_axis=wrong_axis,
            matrix=PrimeFieldMatrix(2, ((1, 0),), 2),
        )
    point = ProjectivePoint(presentation, row_axis, (one, zero))
    assert RankResult(point, matrix).rank == 2


def test_subspace_rejects_dependent_basis_matrices() -> None:
    presentation = _presentation()
    rows = Axis("rows", ("r1", "r2"))
    columns = Axis("columns", ("c1", "c2"))
    basis_axis = Axis("basis", ("B1", "B2"))
    zero = _element(presentation, (0, 0, 0))
    one = _element(presentation, (1, 0, 0))
    matrix = AxisBoundMatrix(
        presentation,
        rows,
        columns,
        ((one, zero), (zero, zero)),
    )

    with pytest.raises(ValueError, match="independent"):
        FiniteDimensionalSubspace(
            presentation=presentation,
            basis_axis=basis_axis,
            basis=(matrix, matrix),
        )
