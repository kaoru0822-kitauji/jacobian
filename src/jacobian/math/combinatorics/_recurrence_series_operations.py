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
    """Materialize the complete bounded replay prefix and requested projection."""

    requested_indices = (
        tuple(range(request.term_count))
        if request.scope == "PREFIX" and request.term_count is not None
        else request.indices
    )
    replay_scope_end = requested_indices[-1]
    replay = _admit_linear_recurrence(
        coefficients=request.coefficients,
        initial_values=request.initial_values,
        coefficient_convention=request.coefficient_convention,
        scope=request.scope,
        requested_indices=requested_indices,
    )
    replay_wire = tuple(_wire(item) for item in replay)
    return LinearRecurrenceEvaluationResult._from_kernel(
        coefficient_convention=request.coefficient_convention,
        scope=request.scope,
        values=tuple(
            IndexedRationalValue(index=index, value=replay_wire[index])
            for index in requested_indices
        ),
        replay_prefix=replay_wire,
        replay_scope_end=replay_scope_end,
    )


def evaluate_polynomial_coefficient_recurrence(
    request: PolynomialCoefficientRecurrenceEvaluationRequest,
) -> PolynomialCoefficientRecurrenceEvaluationResult:
    """Evaluate and expose residuals for a bounded P-recursive relation."""

    requested_indices = (
        tuple(range(request.term_count))
        if request.scope == "PREFIX" and request.term_count is not None
        else request.indices
    )
    end = requested_indices[-1]
    replay, residual_pairs = _admit_p_recursive_recurrence(
        coefficient_polynomials=request.coefficient_polynomials,
        initial_values=request.initial_values,
        coefficient_convention=request.coefficient_convention,
        polynomial_convention=request.polynomial_convention,
        scope=request.scope,
        requested_indices=requested_indices,
    )
    order = len(request.coefficient_polynomials) - 1
    residuals = tuple(
        IndexedRationalValue(index=index, value=_wire(value))
        for index, value in residual_pairs
    )
    replay_wire = tuple(_wire(item) for item in replay)
    return PolynomialCoefficientRecurrenceEvaluationResult._from_kernel(
        coefficient_convention=request.coefficient_convention,
        polynomial_convention=request.polynomial_convention,
        scope=request.scope,
        recurrence_order=order,
        values=tuple(
            IndexedRationalValue(index=index, value=replay_wire[index])
            for index in requested_indices
        ),
        replay_prefix=replay_wire,
        residuals=residuals,
        replay_scope_end=end,
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
