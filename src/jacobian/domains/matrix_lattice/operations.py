"""Thin SymPy projections for exact matrix operations."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import sympy
from sympy.matrices.normalforms import smith_normal_form

from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.matrix_operations import (
    CharacteristicPolynomialResult,
    IntegerMatrix,
    IntegerMatrixRequest,
    MatrixInverseResult,
    MatrixTraceResult,
    NullspaceResult,
    RationalMatrix,
    RationalMatrixRequest,
    RrefResult,
    SmithNormalFormResult,
    SquareRationalMatrixRequest,
)


def _rational(value: Any) -> CanonicalRational:
    fraction = Fraction(value)
    return CanonicalRational(
        num=str(fraction.numerator),
        den=str(fraction.denominator),
    )


def _qq_matrix(matrix: RationalMatrix) -> sympy.Matrix:
    return sympy.Matrix(
        [
            [sympy.Rational(int(value.num), int(value.den)) for value in row]
            for row in matrix.entries
        ]
    )


def compute_rref(request: RationalMatrixRequest) -> RrefResult:
    reduced, pivots = _qq_matrix(request.matrix).rref()
    columns = reduced.cols
    pivot_columns = tuple(int(column) for column in pivots)
    return RrefResult(
        reduced_matrix=RationalMatrix(
            entries=tuple(
                tuple(_rational(reduced[row, column]) for column in range(columns))
                for row in range(reduced.rows)
            )
        ),
        rank=len(pivot_columns),
        pivot_columns=pivot_columns,
        free_columns=tuple(
            column for column in range(columns) if column not in pivot_columns
        ),
    )


def compute_nullspace(request: RationalMatrixRequest) -> NullspaceResult:
    matrix = _qq_matrix(request.matrix)
    reduced, pivots = matrix.rref()
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
        basis.append(tuple(_rational(value) for value in vector))
    return NullspaceResult(
        ambient_dimension=matrix.cols,
        nullity=len(basis),
        basis_vectors=tuple(basis),
        free_columns=free_columns,
    )


def compute_characteristic_polynomial(
    request: SquareRationalMatrixRequest,
) -> CharacteristicPolynomialResult:
    polynomial = _qq_matrix(request.matrix).charpoly("lambda")
    return CharacteristicPolynomialResult(
        degree=polynomial.degree(),
        coefficients_descending=tuple(
            _rational(coefficient) for coefficient in polynomial.all_coeffs()
        ),
    )


def compute_smith_normal_form(
    request: IntegerMatrixRequest,
) -> SmithNormalFormResult:
    source = sympy.Matrix(
        [[int(value) for value in row] for row in request.matrix.entries]
    )
    raw = smith_normal_form(source, domain=sympy.ZZ)
    diagonal_count = min(raw.rows, raw.cols)
    factors = tuple(abs(int(raw[index, index])) for index in range(diagonal_count))
    invariant_factors = tuple(value for value in factors if value)
    canonical = sympy.zeros(raw.rows, raw.cols)
    for index, value in enumerate(invariant_factors):
        canonical[index, index] = value
    return SmithNormalFormResult(
        normal_form=IntegerMatrix(
            entries=tuple(
                tuple(str(int(canonical[row, column])) for column in range(raw.cols))
                for row in range(raw.rows)
            )
        ),
        rank=len(invariant_factors),
        invariant_factors=tuple(str(value) for value in invariant_factors),
    )


def compute_inverse(request: IntegerMatrixRequest) -> MatrixInverseResult:
    source = sympy.Matrix(
        [[int(value) for value in row] for row in request.matrix.entries]
    )
    if source.rows != source.cols:
        raise ValueError("inverse requires a square matrix")
    if source.det() == 0:
        raise ValueError("matrix is singular; inverse does not exist")
    inverse = source.inv()
    return MatrixInverseResult(
        inverse=RationalMatrix(
            entries=tuple(
                tuple(_rational(inverse[row, column]) for column in range(inverse.cols))
                for row in range(inverse.rows)
            )
        )
    )


def compute_trace(request: IntegerMatrixRequest) -> MatrixTraceResult:
    source = sympy.Matrix(
        [[int(value) for value in row] for row in request.matrix.entries]
    )
    if source.rows != source.cols:
        raise ValueError("trace requires a square matrix")
    return MatrixTraceResult(trace=str(int(source.trace())))
