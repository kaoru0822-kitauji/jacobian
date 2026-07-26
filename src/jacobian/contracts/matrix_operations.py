"""Bounded exact matrix-operation contracts."""

from __future__ import annotations

from itertools import pairwise
from typing import Literal, Self

from pydantic import Field, StrictInt, model_validator

from jacobian.contracts.exact import CanonicalInteger, CanonicalRational
from jacobian.contracts.results import ContractModel

MAX_MATRIX_DIMENSION = 32
MAX_SCALAR_DIGITS = 256


def _check_integer_digits(value: str) -> None:
    if len(value.lstrip("-")) > MAX_SCALAR_DIGITS:
        raise ValueError("matrix scalars are limited to 256 decimal digits")


class RationalMatrix(ContractModel):
    """One nonempty rectangular matrix over canonical rationals."""

    domain: Literal["QQ"] = "QQ"
    entries: tuple[tuple[CanonicalRational, ...], ...] = Field(
        min_length=1,
        max_length=MAX_MATRIX_DIMENSION,
    )

    @model_validator(mode="after")
    def require_bounded_rectangle(self) -> Self:
        columns = len(self.entries[0])
        if not 1 <= columns <= MAX_MATRIX_DIMENSION:
            raise ValueError("matrix rows must contain between 1 and 32 entries")
        if any(len(row) != columns for row in self.entries):
            raise ValueError("matrix rows must all have the same length")
        for row in self.entries:
            for value in row:
                _check_integer_digits(value.num)
                _check_integer_digits(value.den)
        return self


class IntegerMatrix(ContractModel):
    """One nonempty rectangular matrix over canonical integers."""

    domain: Literal["ZZ"] = "ZZ"
    entries: tuple[tuple[CanonicalInteger, ...], ...] = Field(
        min_length=1,
        max_length=MAX_MATRIX_DIMENSION,
    )

    @model_validator(mode="after")
    def require_bounded_rectangle(self) -> Self:
        columns = len(self.entries[0])
        if not 1 <= columns <= MAX_MATRIX_DIMENSION:
            raise ValueError("matrix rows must contain between 1 and 32 entries")
        if any(len(row) != columns for row in self.entries):
            raise ValueError("matrix rows must all have the same length")
        for row in self.entries:
            for value in row:
                _check_integer_digits(value)
        return self


class RationalMatrixRequest(ContractModel):
    matrix: RationalMatrix


class SquareRationalMatrixRequest(ContractModel):
    matrix: RationalMatrix

    @model_validator(mode="after")
    def require_square(self) -> Self:
        if len(self.matrix.entries) != len(self.matrix.entries[0]):
            raise ValueError("characteristic polynomial requires a square matrix")
        return self


class IntegerMatrixRequest(ContractModel):
    matrix: IntegerMatrix


class LatticeReductionBudget(ContractModel):
    """Wall-clock bound for one isolated LLL computation."""

    wall_seconds: StrictInt = Field(default=10, ge=1, le=60)


class LatticeReductionRequest(ContractModel):
    basis: IntegerMatrix
    resource_budget: LatticeReductionBudget = Field(
        default_factory=LatticeReductionBudget
    )


class RrefResult(ContractModel):
    reduced_matrix: RationalMatrix
    rank: int = Field(ge=0, le=MAX_MATRIX_DIMENSION)
    pivot_columns: tuple[int, ...] = Field(max_length=MAX_MATRIX_DIMENSION)
    free_columns: tuple[int, ...] = Field(max_length=MAX_MATRIX_DIMENSION)
    convention: Literal["UNIQUE_RREF_OVER_QQ"] = "UNIQUE_RREF_OVER_QQ"


class NullspaceResult(ContractModel):
    ambient_dimension: int = Field(ge=1, le=MAX_MATRIX_DIMENSION)
    nullity: int = Field(ge=0, le=MAX_MATRIX_DIMENSION)
    basis_vectors: tuple[tuple[CanonicalRational, ...], ...] = Field(
        max_length=MAX_MATRIX_DIMENSION
    )
    free_columns: tuple[int, ...] = Field(max_length=MAX_MATRIX_DIMENSION)
    convention: Literal["RREF_FUNDAMENTAL_BASIS"] = "RREF_FUNDAMENTAL_BASIS"

    @model_validator(mode="after")
    def require_basis_shape(self) -> Self:
        if len(self.basis_vectors) != self.nullity:
            raise ValueError("basis vector count must equal nullity")
        if any(len(vector) != self.ambient_dimension for vector in self.basis_vectors):
            raise ValueError("each basis vector must have the ambient dimension")
        if len(self.free_columns) != self.nullity:
            raise ValueError("free column count must equal nullity")
        return self


class CharacteristicPolynomialResult(ContractModel):
    variable: Literal["lambda"] = "lambda"
    degree: int = Field(ge=1, le=MAX_MATRIX_DIMENSION)
    coefficients_descending: tuple[CanonicalRational, ...] = Field(
        min_length=2,
        max_length=MAX_MATRIX_DIMENSION + 1,
    )
    monic: Literal[True] = True
    convention: Literal["DET_LAMBDA_I_MINUS_A"] = "DET_LAMBDA_I_MINUS_A"

    @model_validator(mode="after")
    def require_dense_monic_coefficients(self) -> Self:
        if len(self.coefficients_descending) != self.degree + 1:
            raise ValueError("dense coefficient count must be degree plus one")
        if self.coefficients_descending[0] != CanonicalRational(num="1", den="1"):
            raise ValueError("characteristic polynomial must be monic")
        return self


class SmithNormalFormResult(ContractModel):
    normal_form: IntegerMatrix
    rank: int = Field(ge=0, le=MAX_MATRIX_DIMENSION)
    invariant_factors: tuple[CanonicalInteger, ...] = Field(
        max_length=MAX_MATRIX_DIMENSION
    )
    transformation_available: Literal[False] = False
    convention: Literal["POSITIVE_DIVISIBILITY_DIAGONAL"] = (
        "POSITIVE_DIVISIBILITY_DIAGONAL"
    )

    @model_validator(mode="after")
    def require_invariant_factor_chain(self) -> Self:
        if len(self.invariant_factors) != self.rank:
            raise ValueError("nonzero invariant factor count must equal rank")
        factors = tuple(int(value) for value in self.invariant_factors)
        if any(value <= 0 for value in factors):
            raise ValueError("Smith invariant factors must be positive")
        if any(right % left != 0 for left, right in pairwise(factors)):
            raise ValueError("each Smith invariant factor must divide the next")
        return self


class MatrixInverseResult(ContractModel):
    inverse: RationalMatrix
    convention: Literal["TWO_SIDED_INVERSE_OVER_QQ"] = "TWO_SIDED_INVERSE_OVER_QQ"


class MatrixTraceResult(ContractModel):
    trace: CanonicalInteger
    convention: Literal["SUM_OF_DIAGONAL_ENTRIES"] = "SUM_OF_DIAGONAL_ENTRIES"


class LatticeReductionResult(ContractModel):
    reduced_basis: IntegerMatrix
    transformation: IntegerMatrix
    rank: int = Field(ge=0, le=MAX_MATRIX_DIMENSION)
    relation: Literal["REDUCED_BASIS_EQUALS_TRANSFORMATION_TIMES_BASIS"] = (
        "REDUCED_BASIS_EQUALS_TRANSFORMATION_TIMES_BASIS"
    )
    representation: Literal["INTEGER_ROW_BASIS"] = "INTEGER_ROW_BASIS"
    gram_mode: Literal["EXACT"] = "EXACT"
    delta: Literal["0.99"] = "0.99"
    eta: Literal["0.51"] = "0.51"

    @model_validator(mode="after")
    def require_transformation_shape(self) -> Self:
        rows = len(self.reduced_basis.entries)
        if len(self.transformation.entries) != rows:
            raise ValueError("LLL transformation must have one row per basis row")
        if len(self.transformation.entries[0]) != rows:
            raise ValueError("LLL transformation must be square by basis row count")
        return self
