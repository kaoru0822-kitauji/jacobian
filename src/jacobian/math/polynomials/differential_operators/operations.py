"""Native exact constant-coefficient differential-operator functions."""

from __future__ import annotations

from pydantic_core import PydanticCustomError

from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.polynomials.differential_operators._bounds import (
    ApplicationEnvelope,
    validate_application_envelope,
)
from jacobian.math.polynomials.differential_operators._flint import apply_with_flint
from jacobian.math.polynomials.differential_operators.values import (
    ConstantCoefficientDifferentialOperator,
)
from jacobian.math.polynomials.values import RationalPolynomial


def _admit_application(
    polynomial: RationalPolynomial,
    operator: ConstantCoefficientDifferentialOperator,
    iterations: int,
    expected: RationalPolynomial | None,
) -> ApplicationEnvelope:
    try:
        return validate_application_envelope(
            polynomial,
            operator,
            iterations,
            expected,
        )
    except OperationDomainValidationError:
        raise
    except PydanticCustomError as exc:
        raise OperationDomainValidationError(
            location=(), code=exc.type, message=exc.message()
        ) from exc
    except (TypeError, ValueError) as exc:
        raise OperationDomainValidationError(
            location=(),
            code="polynomial.differential_operator_admission",
            message=str(exc),
        ) from exc


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
