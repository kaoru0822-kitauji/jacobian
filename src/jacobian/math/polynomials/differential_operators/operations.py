"""Native exact constant-coefficient differential-operator functions."""

from __future__ import annotations

from jacobian.math.polynomials.differential_operators._flint import apply_with_flint
from jacobian.math.polynomials.differential_operators._operations import (
    _admit_application,
)
from jacobian.math.polynomials.differential_operators.values import (
    ConstantCoefficientDifferentialOperator,
)
from jacobian.math.polynomials.values import RationalPolynomial


def apply_constant_coefficient_differential_operator(
    polynomial: RationalPolynomial,
    operator: ConstantCoefficientDifferentialOperator,
    iterations: int = 1,
) -> RationalPolynomial:
    """Return the exact polynomial ``operator**iterations(polynomial)``.

    The polynomial and operator use the same complete ordered variable axis.
    Iteration is finite and request-local; callers own further composition.
    """

    envelope = _admit_application(
        polynomial,
        operator,
        iterations,
        expected=None,
    )
    return apply_with_flint(polynomial, operator, iterations, envelope)


__all__ = ["apply_constant_coefficient_differential_operator"]
