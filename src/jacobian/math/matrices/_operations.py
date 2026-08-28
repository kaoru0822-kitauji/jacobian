"""Thin SymPy projections for exact matrix operations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic_core import PydanticCustomError

from jacobian._exact import CanonicalRational
from jacobian.canonical import format_canonical_integer
from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math import matrices
from jacobian.math.matrices import _conversions as conversions
from jacobian.math.matrices._operation_models import (
    MAX_DETERMINANT_MATRIX_DIMENSION,
    MAX_INPUT_SCALAR_DIGITS,
    MAX_KRONECKER_PRODUCT_AXIS,
    MAX_PERMANENT_RYSER_SUBSETS,
    CharacteristicPolynomialResult,
    IntegerMatrixRequest,
    MatrixAdjugateResult,
    MatrixDeterminantRequest,
    MatrixDeterminantResult,
    MatrixInverseResult,
    MatrixKroneckerProductRequest,
    MatrixKroneckerProductResult,
    MatrixPartialTraceRequest,
    MatrixPartialTraceResult,
    MatrixPermanentRequest,
    MatrixPermanentResult,
    MatrixProductResult,
    MatrixRankRequest,
    MatrixRankResult,
    MatrixTraceResult,
    NonsingularIntegerMatrixRequest,
    NullspaceResult,
    RationalLinearSolveRequest,
    RationalLinearSolveResult,
    RationalMatrixProductRequest,
    RationalMatrixRequest,
    RrefResult,
    SquareIntegerMatrixRequest,
    SquareRationalMatrixRequest,
    _require_computation_dimensions,
    _require_square_system_admission,
    _validation_error,
)
from jacobian.math.matrices.operations import MatrixSingularError
from jacobian.math.matrices.values import RationalMatrix, SmithNormalForm


def _admit(request: Any, check: Callable[[Any], None]) -> None:
    try:
        check(request)
    except PydanticCustomError as exc:
        raise OperationDomainValidationError(
            location=("request",), code=exc.type, message=exc.message()
        ) from exc


def _admit_rational_matrix(matrix: RationalMatrix) -> None:
    _require_computation_dimensions(matrix.entries)
    from jacobian.math.matrices.values import require_matrix_scalar_digits

    require_matrix_scalar_digits(
        matrix.entries, maximum=MAX_INPUT_SCALAR_DIGITS, label="matrix input"
    )


def _admit_rational(request: RationalMatrixRequest | MatrixRankRequest) -> None:
    _admit_rational_matrix(request.matrix)


def _admit_square_rational(request: Any) -> None:
    matrix = request.matrix
    _admit_rational_matrix(matrix)
    if len(matrix.entries) != len(matrix.entries[0]):
        raise _validation_error("budget_exceeded", "operation requires a square matrix")


def _admit_integer(request: Any) -> None:
    from jacobian.math.matrices.values import require_matrix_scalar_digits

    require_matrix_scalar_digits(
        request.matrix.entries,
        maximum=MAX_INPUT_SCALAR_DIGITS,
        label="matrix input",
    )


def _admit_square_integer(request: Any) -> None:
    _admit_integer(request)
    matrix = request.matrix
    rows = len(matrix.entries)
    if rows == 0 or rows != len(matrix.entries[0]):
        raise _validation_error(
            "budget_exceeded", "operation requires a square integer matrix"
        )


def _admit_permanent(request: Any) -> None:
    _admit_integer(request)
    matrix = request.matrix
    order = len(matrix.entries)
    if order != len(matrix.entries[0]):
        raise _validation_error(
            "budget_exceeded", "permanent computation requires a square matrix"
        )
    if (1 << order) > MAX_PERMANENT_RYSER_SUBSETS:
        raise _validation_error(
            "budget_exceeded",
            "permanent computation exceeds the "
            f"{MAX_PERMANENT_RYSER_SUBSETS}-subset Ryser work budget",
        )


def _admit_product(request: Any) -> None:
    left = request.left
    right = request.right
    if len(left.entries[0]) != len(right.entries):
        raise _validation_error(
            "budget_exceeded",
            "matrix multiplication requires the left column count to equal the right row count",
        )
    _admit_rational_matrix(left)
    _admit_rational_matrix(right)


def _admit_kronecker(request: Any) -> None:
    left = request.left
    right = request.right
    _admit_rational_matrix(left)
    _admit_rational_matrix(right)
    if (
        len(left.entries) * len(right.entries) > MAX_KRONECKER_PRODUCT_AXIS
        or len(left.entries[0]) * len(right.entries[0]) > MAX_KRONECKER_PRODUCT_AXIS
    ):
        raise _validation_error(
            "budget_exceeded",
            "kronecker products must fit within "
            f"{MAX_KRONECKER_PRODUCT_AXIS} rows and columns",
        )


def _admit_partial_trace(request: Any) -> None:
    matrix = request.matrix
    _admit_rational_matrix(matrix)
    total = request.traced_dimension * request.kept_dimension
    if len(matrix.entries) != total or len(matrix.entries[0]) != total:
        raise _validation_error(
            "budget_exceeded",
            "composite matrix must be square of order traced_dimension * kept_dimension",
        )


def _admit_determinant(request: Any) -> None:
    _admit_square_rational(request)
    if len(request.matrix.entries) > MAX_DETERMINANT_MATRIX_DIMENSION:
        raise _validation_error(
            "budget_exceeded",
            "determinant matrices are limited to order "
            f"{MAX_DETERMINANT_MATRIX_DIMENSION}",
        )


def _admit_linear_solve(request: RationalLinearSolveRequest) -> None:
    _require_square_system_admission(request.matrix, request.rhs)


def compute_determinant(
    request: MatrixDeterminantRequest,
) -> MatrixDeterminantResult:
    _admit(request, _admit_determinant)
    determinant = matrices.determinant(
        conversions.rational_matrix_to_sympy(request.matrix)
    )
    return MatrixDeterminantResult(
        determinant=conversions.rational_from_sympy(determinant)
    )


def compute_rank(request: MatrixRankRequest) -> MatrixRankResult:
    _admit(request, _admit_rational)
    rank, pivot_columns = matrices.rank(
        conversions.rational_matrix_to_sympy(request.matrix)
    )
    return MatrixRankResult._from_kernel(
        matrix=request.matrix,
        rank=rank,
        pivot_columns=tuple(int(column) for column in pivot_columns),
    )


def compute_rref(request: RationalMatrixRequest) -> RrefResult:
    _admit(request, _admit_rational)
    reduced, pivots = matrices.rref(
        conversions.rational_matrix_to_sympy(request.matrix)
    )
    columns = reduced.cols
    pivot_columns = tuple(int(column) for column in pivots)
    return RrefResult._from_kernel(
        matrix=request.matrix,
        reduced_matrix=conversions.rational_matrix_from_sympy(reduced),
        rank=len(pivot_columns),
        pivot_columns=pivot_columns,
        free_columns=tuple(
            column for column in range(columns) if column not in pivot_columns
        ),
    )


def compute_nullspace(request: RationalMatrixRequest) -> NullspaceResult:
    _admit(request, _admit_rational)
    import sympy

    matrix = conversions.rational_matrix_to_sympy(request.matrix)
    reduced, pivots = matrices.rref(matrix)
    pivot_columns = tuple(int(column) for column in pivots)
    free_columns = tuple(
        column for column in range(matrix.cols) if column not in pivot_columns
    )
    pivot_row_by_column = {
        pivot_column: row for row, pivot_column in enumerate(pivot_columns)
    }
    basis: list[tuple[CanonicalRational, ...]] = []
    for free_column in free_columns:
        vector = [sympy.S.Zero] * matrix.cols
        vector[free_column] = sympy.S.One
        for pivot_column, row in pivot_row_by_column.items():
            vector[pivot_column] = -reduced[row, free_column]
        basis.append(tuple(conversions.rational_from_sympy(value) for value in vector))
    return NullspaceResult._from_kernel(
        matrix=request.matrix,
        ambient_dimension=matrix.cols,
        rank=len(pivot_columns),
        nullity=len(basis),
        basis_vectors=tuple(basis),
        free_columns=free_columns,
    )


def compute_characteristic_polynomial(
    request: SquareRationalMatrixRequest,
) -> CharacteristicPolynomialResult:
    _admit(request, _admit_square_rational)
    polynomial = matrices.characteristic_polynomial(
        conversions.rational_matrix_to_sympy(request.matrix), "lambda"
    )
    return CharacteristicPolynomialResult(
        degree=polynomial.degree(),
        coefficients_descending=tuple(
            conversions.rational_from_sympy(coefficient)
            for coefficient in polynomial.all_coeffs()
        ),
    )


def compute_smith_normal_form(
    request: IntegerMatrixRequest,
) -> SmithNormalForm:
    _admit(request, _admit_integer)
    raw = matrices.smith_normal_form(
        conversions.integer_matrix_to_sympy(request.matrix)
    )
    return conversions.smith_normal_form_from_sympy(raw)


def compute_inverse(request: NonsingularIntegerMatrixRequest) -> MatrixInverseResult:
    _admit(request, _admit_square_integer)
    try:
        inverse = matrices.inverse(conversions.integer_matrix_to_sympy(request.matrix))
    except MatrixSingularError as exc:
        raise OperationDomainValidationError(
            location=("matrix",),
            code="matrix.singular_matrix",
            message="matrix is singular; inverse does not exist",
        ) from exc
    return MatrixInverseResult(inverse=conversions.rational_matrix_from_sympy(inverse))


def compute_trace(request: SquareIntegerMatrixRequest) -> MatrixTraceResult:
    _admit(request, _admit_square_integer)
    return MatrixTraceResult(
        trace=format_canonical_integer(
            matrices.trace(conversions.integer_matrix_to_sympy(request.matrix))
        )
    )


def compute_product(request: RationalMatrixProductRequest) -> MatrixProductResult:
    _admit(request, _admit_product)
    left = conversions.rational_matrix_to_sympy(request.left)
    right = conversions.rational_matrix_to_sympy(request.right)
    product = matrices.multiply(left, right)
    return MatrixProductResult(
        product=conversions.rational_matrix_from_sympy(product),
        left_rows=left.rows,
        inner_dimension=left.cols,
        right_columns=right.cols,
    )


def compute_rational_linear_solve(
    request: RationalLinearSolveRequest,
) -> RationalLinearSolveResult:
    _admit(request, _admit_linear_solve)
    import sympy

    source = conversions.rational_matrix_to_sympy(request.matrix)
    rhs = sympy.Matrix([sympy.Rational(value.as_fraction()) for value in request.rhs])
    try:
        solution, parameters = matrices.solve_linear_system(source, rhs)
    except ValueError:
        return RationalLinearSolveResult._from_kernel(
            matrix=request.matrix,
            rhs=request.rhs,
            outcome="INCONSISTENT",
        )
    if parameters.rows:
        return RationalLinearSolveResult._from_kernel(
            matrix=request.matrix,
            rhs=request.rhs,
            outcome="NON_UNIQUE",
        )
    return RationalLinearSolveResult._from_kernel(
        matrix=request.matrix,
        rhs=request.rhs,
        outcome="UNIQUE",
        solution=tuple(conversions.rational_from_sympy(value) for value in solution),
    )


def compute_adjugate(request: SquareIntegerMatrixRequest) -> MatrixAdjugateResult:
    _admit(request, _admit_square_integer)
    adjugate = matrices.adjugate(conversions.integer_matrix_to_sympy(request.matrix))
    return MatrixAdjugateResult(
        adjugate=conversions.integer_matrix_from_sympy(adjugate)
    )


def compute_permanent(request: MatrixPermanentRequest) -> MatrixPermanentResult:
    _admit(request, _admit_permanent)
    value = matrices.permanent(conversions.rational_matrix_to_sympy(request.matrix))
    return MatrixPermanentResult(
        permanent=conversions.rational_from_sympy(value),
    )


def compute_kronecker_product(
    request: MatrixKroneckerProductRequest,
) -> MatrixKroneckerProductResult:
    _admit(request, _admit_kronecker)
    left = conversions.rational_matrix_to_sympy(request.left)
    right = conversions.rational_matrix_to_sympy(request.right)
    product = matrices.kronecker_product(left, right)
    return MatrixKroneckerProductResult(
        product=conversions.rational_matrix_from_sympy(product),
        left_rows=left.rows,
        left_columns=left.cols,
        right_rows=right.rows,
        right_columns=right.cols,
    )


def compute_partial_trace(
    request: MatrixPartialTraceRequest,
) -> MatrixPartialTraceResult:
    _admit(request, _admit_partial_trace)
    matrix = conversions.rational_matrix_to_sympy(request.matrix)
    reduced = matrices.partial_trace(
        matrix,
        request.traced_dimension,
        request.kept_dimension,
    )
    return MatrixPartialTraceResult(
        reduced_matrix=conversions.rational_matrix_from_sympy(reduced),
        traced_dimension=request.traced_dimension,
        kept_dimension=request.kept_dimension,
    )
