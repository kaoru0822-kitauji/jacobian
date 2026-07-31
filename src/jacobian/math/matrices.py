"""Exact linear algebra on SymPy matrices."""

from typing import Any

import sympy
from sympy.matrices.matrixbase import MatrixBase

__all__ = ["inverse", "rref", "trace"]


def _matrix(value: MatrixBase) -> MatrixBase:
    if not isinstance(value, MatrixBase):
        raise TypeError("matrix must be a SymPy MatrixBase")
    if not 1 <= value.rows <= 32 or not 1 <= value.cols <= 32:
        raise ValueError("matrix dimensions must be between 1 and 32")
    if any(not entry.is_number or entry.is_finite is not True for entry in value):
        raise ValueError("matrix entries must be finite exact numbers")
    if any(entry.has(sympy.Float) for entry in value):
        raise ValueError("matrix entries must be exact; SymPy Float is not supported")
    return value


def rref(matrix: MatrixBase) -> tuple[MatrixBase, tuple[int, ...]]:
    """Return exact reduced row-echelon form and pivot columns."""

    reduced, pivots = _matrix(matrix).rref()
    return reduced, tuple(int(pivot) for pivot in pivots)


def inverse(matrix: MatrixBase) -> MatrixBase:
    """Return the exact inverse of a square, nonsingular matrix."""

    source = _matrix(matrix)
    if source.rows != source.cols:
        raise ValueError("inverse requires a square matrix")
    if source.det() == 0:
        raise ValueError("matrix is singular; inverse does not exist")
    return source.inv()


def trace(matrix: MatrixBase) -> Any:
    """Return the exact trace of a square matrix."""

    source = _matrix(matrix)
    if source.rows != source.cols:
        raise ValueError("trace requires a square matrix")
    return sympy.simplify(source.trace())
