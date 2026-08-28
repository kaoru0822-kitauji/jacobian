"""Exact bounded recurrence and rational-series producers."""

from __future__ import annotations

from fractions import Fraction

from jacobian._exact import CanonicalRational
from jacobian.canonical import format_canonical_integer
from jacobian.math.combinatorics._recurrence_admission import (
    _admit_linear_recurrence,
    _admit_p_recursive_recurrence,
    _admit_series,
)
from jacobian.math.combinatorics._recurrence_models import (
    IndexedRationalValue,
    LinearRecurrenceEvaluationRequest,
    LinearRecurrenceEvaluationResult,
    PolynomialCoefficientRecurrenceEvaluationRequest,
    PolynomialCoefficientRecurrenceEvaluationResult,
    RationalGeneratingFunctionCoefficientsRequest,
    RationalGeneratingFunctionCoefficientsResult,
)


def _wire(value: Fraction) -> CanonicalRational:
    return CanonicalRational(
        num=format_canonical_integer(value.numerator),
        den=format_canonical_integer(value.denominator),
    )


def evaluate_linear_recurrence(
    request: LinearRecurrenceEvaluationRequest,
) -> LinearRecurrenceEvaluationResult:
    """Evaluate a bounded recurrence and return the requested projection."""

    requested_indices = (
        tuple(range(request.term_count))
        if request.scope == "PREFIX" and request.term_count is not None
        else request.indices
    )
    prefix = _admit_linear_recurrence(
        coefficients=request.coefficients,
        initial_values=request.initial_values,
        coefficient_convention=request.coefficient_convention,
        scope=request.scope,
        requested_indices=requested_indices,
    )
    return LinearRecurrenceEvaluationResult._from_kernel(
        coefficient_convention=request.coefficient_convention,
        scope=request.scope,
        values=tuple(
            IndexedRationalValue(index=index, value=_wire(prefix[index]))
            for index in requested_indices
        ),
    )


def evaluate_polynomial_coefficient_recurrence(
    request: PolynomialCoefficientRecurrenceEvaluationRequest,
) -> PolynomialCoefficientRecurrenceEvaluationResult:
    """Evaluate a bounded P-recursive relation at the requested indices."""

    requested_indices = (
        tuple(range(request.term_count))
        if request.scope == "PREFIX" and request.term_count is not None
        else request.indices
    )
    prefix = _admit_p_recursive_recurrence(
        coefficient_polynomials=request.coefficient_polynomials,
        initial_values=request.initial_values,
        coefficient_convention=request.coefficient_convention,
        polynomial_convention=request.polynomial_convention,
        scope=request.scope,
        requested_indices=requested_indices,
    )
    order = len(request.coefficient_polynomials) - 1
    return PolynomialCoefficientRecurrenceEvaluationResult._from_kernel(
        coefficient_convention=request.coefficient_convention,
        polynomial_convention=request.polynomial_convention,
        scope=request.scope,
        recurrence_order=order,
        values=tuple(
            IndexedRationalValue(index=index, value=_wire(prefix[index]))
            for index in requested_indices
        ),
    )


def compute_rational_generating_function_coefficients(
    request: RationalGeneratingFunctionCoefficientsRequest,
) -> RationalGeneratingFunctionCoefficientsResult:
    """Expand N(x)/D(x) by exact coefficient recurrence through x^(k-1)."""

    coefficients = _admit_series(
        numerator=request.numerator,
        denominator=request.denominator,
        coefficient_convention=request.coefficient_convention,
        expansion_point=request.expansion_point,
        truncation_order=request.truncation_order,
    )
    return RationalGeneratingFunctionCoefficientsResult._from_kernel(
        coefficient_convention=request.coefficient_convention,
        expansion_point=request.expansion_point,
        truncation_order=request.truncation_order,
        coefficients=tuple(_wire(item) for item in coefficients),
        residual_congruence=(
            "DENOMINATOR_TIMES_SERIES_MINUS_NUMERATOR_IS_ZERO_MOD_X_TO_ORDER"
        ),
        residual_coefficients=tuple(
            CanonicalRational(num="0", den="1") for _ in coefficients
        ),
    )


__all__ = [
    "compute_rational_generating_function_coefficients",
    "evaluate_linear_recurrence",
    "evaluate_polynomial_coefficient_recurrence",
]
