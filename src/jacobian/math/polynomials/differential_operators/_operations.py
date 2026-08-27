"""Catalog adapter for differential-operator application."""

from __future__ import annotations

from jacobian.math.polynomials.differential_operators._flint import apply_with_flint
from jacobian.math.polynomials.differential_operators._models import (
    DifferentialOperatorApplyRequest,
    DifferentialOperatorApplyResult,
)
from jacobian.math.polynomials.differential_operators.operations import (
    _admit_application,
)


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
