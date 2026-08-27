"""Catalog adapter for differential-operator application."""

from __future__ import annotations

from pydantic_core import PydanticCustomError

from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.polynomials.differential_operators._bounds import (
    ApplicationEnvelope,
    validate_application_envelope,
)
from jacobian.math.polynomials.differential_operators._flint import apply_with_flint
from jacobian.math.polynomials.differential_operators._models import (
    DifferentialOperatorApplyRequest,
    DifferentialOperatorApplyResult,
)
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


def compute_differential_operator_application(
    request: DifferentialOperatorApplyRequest,
) -> DifferentialOperatorApplyResult:
    """Apply the admitted operator power and return its source-bound result."""

    envelope = _admit_application(
        request.polynomial,
        request.operator,
        request.iterations,
        request.expected,
    )
    output = apply_with_flint(
        request.polynomial,
        request.operator,
        request.iterations,
        envelope,
    )
    return DifferentialOperatorApplyResult._from_kernel(request, output)


__all__ = ["compute_differential_operator_application"]
