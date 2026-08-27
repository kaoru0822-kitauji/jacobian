"""Domain adapter for exact canonical-form operations."""

from __future__ import annotations

from collections.abc import Sequence
from fractions import Fraction

from pydantic_core import PydanticCustomError

from jacobian._exact import MAX_CANONICAL_RATIONAL_DIGITS, CanonicalRational
from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.matrices.canonical_forms._models import (
    MATRIX_POLYNOMIAL_EVALUATION_PASSES,
    MAX_CANONICAL_FORM_DIMENSION,
    MAX_CANONICAL_FORM_SCALAR_DIGITS,
    MAX_MATRIX_POLYNOMIAL_DIGIT_WORK,
    MAX_MATRIX_POLYNOMIAL_SCALAR_PRODUCTS,
    InvariantFactorEntry,
    MatrixPolynomialEvaluationRequest,
    MatrixPolynomialEvaluationResult,
    MinimalPolynomialResult,
    MonicPolynomial,
    PrimaryDecompositionResult,
    RationalCanonicalFormResult,
    SquareMatrixRequest,
    _polynomial_degree,
    _require_matrix_polynomial_output_budget,
    _validation_error,
)
from jacobian.math.matrices.canonical_forms.operations import (
    _evaluate_polynomial,
    characteristic_polynomial,
    invariant_factors,
    minimal_polynomial,
    primary_decomposition,
)
from jacobian.math.matrices.values import (
    RationalMatrix,
    rational_matrix_from_fractions,
    require_matrix_scalar_digits,
)
from jacobian.math.polynomials.values import (
    MAX_POLYNOMIAL_EXPONENT,
    MAX_POLYNOMIAL_TERMS,
    require_polynomial_budget,
)


def _admit_matrix_polynomial_evaluation(
    request: MatrixPolynomialEvaluationRequest,
) -> None:
    dimension = len(request.matrix.entries)
    if len(request.matrix.entries[0]) != dimension:
        raise _validation_error(
            "budget_exceeded",
            "matrix polynomial evaluation requires a square matrix",
        )
    if len(request.polynomial.variables) != 1:
        raise _validation_error(
            "budget_exceeded",
            "matrix polynomial evaluation requires exactly one polynomial variable",
        )
    require_polynomial_budget(
        request.polynomial,
        maximum_terms=MAX_POLYNOMIAL_TERMS,
        maximum_exponent=MAX_POLYNOMIAL_EXPONENT,
        maximum_coefficient_digits=MAX_CANONICAL_RATIONAL_DIGITS,
        label="matrix polynomial",
    )
    degree = _polynomial_degree(request.polynomial)
    scalar_products_per_pass = degree * dimension**3
    total_scalar_products = MATRIX_POLYNOMIAL_EVALUATION_PASSES * scalar_products_per_pass
    if total_scalar_products > MAX_MATRIX_POLYNOMIAL_SCALAR_PRODUCTS:
        raise _validation_error(
            "budget_exceeded",
            "matrix polynomial Horner evaluation and retained-source accounting "
            f"exceed the {MAX_MATRIX_POLYNOMIAL_SCALAR_PRODUCTS:,}-scalar-product "
            "work bound",
        )
    maximum_arithmetic_digits = _require_matrix_polynomial_output_budget(
        request.matrix,
        request.polynomial,
        degree,
    )
    digit_work = total_scalar_products * maximum_arithmetic_digits**2
    if digit_work > MAX_MATRIX_POLYNOMIAL_DIGIT_WORK:
        raise _validation_error(
            "budget_exceeded",
            "matrix polynomial exact-arithmetic work exceeds the coupled "
            f"{MAX_MATRIX_POLYNOMIAL_DIGIT_WORK:,}-unit digit-work bound",
        )


def _admit_square_matrix(request: SquareMatrixRequest) -> None:
    rows = len(request.matrix.entries)
    columns = len(request.matrix.entries[0])
    if rows != columns:
        raise _validation_error(
            "budget_exceeded", "canonical-form operations require a square matrix"
        )
    if rows > MAX_CANONICAL_FORM_DIMENSION:
        raise _validation_error(
            "budget_exceeded",
            f"canonical-form operations are bounded to {MAX_CANONICAL_FORM_DIMENSION} x "
            f"{MAX_CANONICAL_FORM_DIMENSION} matrices",
        )
    require_matrix_scalar_digits(
        request.matrix.entries,
        maximum=MAX_CANONICAL_FORM_SCALAR_DIGITS,
        label="canonical-form matrix",
    )


def _admit(request: MatrixPolynomialEvaluationRequest | SquareMatrixRequest) -> None:
    try:
        if isinstance(request, MatrixPolynomialEvaluationRequest):
            _admit_matrix_polynomial_evaluation(request)
        else:
            _admit_square_matrix(request)
    except PydanticCustomError as exc:
        raise OperationDomainValidationError(
            location=("matrix",), code=exc.type, message=exc.message()
        ) from exc
    except ValueError as exc:
        raise OperationDomainValidationError(
            location=("matrix",), code="matrix.domain_invalid", message=str(exc)
        ) from exc


def _matrix_entries(
    matrix: RationalMatrix,
) -> tuple[tuple[Fraction, ...], ...]:
    return tuple(tuple(value.as_fraction() for value in row) for row in matrix.entries)


def _to_monic_polynomial(coefficients: Sequence[Fraction]) -> MonicPolynomial:
    return MonicPolynomial(
        coefficients=tuple(
            CanonicalRational.from_fraction(coefficient) for coefficient in coefficients
        )
    )


def _dense_polynomial_coefficients(
    request: MatrixPolynomialEvaluationRequest,
) -> tuple[Fraction, ...]:
    degree = max(
        (term.exponents[0] for term in request.polynomial.polynomial.terms),
        default=0,
    )
    coefficients = [Fraction(0)] * (degree + 1)
    for term in request.polynomial.polynomial.terms:
        coefficients[term.exponents[0]] = term.coefficient.as_fraction()
    return tuple(coefficients)


def evaluate_matrix_polynomial_value(
    request: MatrixPolynomialEvaluationRequest,
) -> RationalMatrix:
    _admit(request)
    return _evaluate_matrix_polynomial_value(request)


def _evaluate_matrix_polynomial_value(
    request: MatrixPolynomialEvaluationRequest,
) -> RationalMatrix:
    evaluated = _evaluate_polynomial(
        _matrix_entries(request.matrix),
        _dense_polynomial_coefficients(request),
    )
    return rational_matrix_from_fractions(evaluated)


def compute_matrix_polynomial_evaluation(
    request: MatrixPolynomialEvaluationRequest,
) -> MatrixPolynomialEvaluationResult:
    _admit(request)
    return MatrixPolynomialEvaluationResult._from_kernel(
        request=request,
        value=_evaluate_matrix_polynomial_value(request),
    )


def compute_minimal_polynomial(
    request: SquareMatrixRequest,
) -> MinimalPolynomialResult:
    _admit(request)
    entries = _matrix_entries(request.matrix)
    minimal = minimal_polynomial(entries)
    characteristic = characteristic_polynomial(entries)
    return MinimalPolynomialResult._from_kernel(
        matrix=request,
        minimal_polynomial=_to_monic_polynomial(minimal),
        characteristic_polynomial=_to_monic_polynomial(characteristic),
    )


def compute_rational_canonical_form(
    request: SquareMatrixRequest,
) -> RationalCanonicalFormResult:
    _admit(request)
    entries = _matrix_entries(request.matrix)
    factors = invariant_factors(entries)
    minimal = minimal_polynomial(entries)
    characteristic = characteristic_polynomial(entries)

    invariant_entries = tuple(
        InvariantFactorEntry(
            factor=_to_monic_polynomial(coefficients),
            block_size=len(coefficients) - 1,
        )
        for coefficients in factors
    )

    return RationalCanonicalFormResult._from_kernel(
        matrix=request,
        invariant_factors=invariant_entries,
        characteristic_polynomial=_to_monic_polynomial(characteristic),
        minimal_polynomial=_to_monic_polynomial(minimal),
    )


def compute_primary_decomposition(
    request: SquareMatrixRequest,
) -> PrimaryDecompositionResult:
    _admit(request)
    entries = _matrix_entries(request.matrix)
    components = primary_decomposition(entries)
    minimal = minimal_polynomial(entries)
    return PrimaryDecompositionResult._from_kernel(
        matrix=request,
        components=tuple(
            _to_monic_polynomial(coefficient) for coefficient in components
        ),
        minimal_polynomial=_to_monic_polynomial(minimal),
    )
