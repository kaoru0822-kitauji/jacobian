"""Private python-flint conversions for exact finite-field arithmetic."""

from __future__ import annotations

from typing import Any

from jacobian.math.finite_fields.values import (
    FiniteFieldElement,
    FiniteFieldPresentation,
)
from jacobian.math.prime_field_linear_algebra import PrimeFieldMatrix


def context(presentation: FiniteFieldPresentation) -> Any:
    from flint import fmpz_mod_poly_ctx, fq_default_ctx

    modulus = fmpz_mod_poly_ctx(presentation.characteristic)(
        list(presentation.modulus_coefficients)
    )
    result = fq_default_ctx(modulus=modulus)
    recovered = tuple(int(value) for value in result.modulus().coeffs())
    if recovered != presentation.modulus_coefficients:
        raise ValueError("python-flint did not preserve the exact field modulus")
    expected_generator = (0, 1) + (0,) * (presentation.degree - 2)
    if tuple(int(value) for value in result.gen().to_list()) != expected_generator:
        raise ValueError("python-flint did not preserve the power-basis generator")
    return result


def to_backend(element: FiniteFieldElement, *, active_context: Any) -> Any:
    return active_context(list(element.coordinates))


def coordinates(value: Any, *, degree: int) -> tuple[int, ...]:
    result = tuple(int(coordinate) for coordinate in value.to_list())
    if len(result) > degree:
        raise ValueError("python-flint returned too many element coordinates")
    return result + (0,) * (degree - len(result))


def matrix_rank(matrix: PrimeFieldMatrix) -> int:
    """Compute rank with python-flint's maintained prime-field matrix type."""

    if not matrix.entries or matrix.columns == 0:
        return 0
    from flint import nmod_mat

    backend = nmod_mat([list(row) for row in matrix.entries], matrix.prime)
    return int(backend.rank())
