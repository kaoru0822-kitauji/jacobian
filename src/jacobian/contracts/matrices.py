"""Exact rational matrix capability contracts."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from jacobian.contracts.common import ArtifactUri
from jacobian.contracts.exact import CanonicalRational
from jacobian.contracts.results import ContractModel


class ExactRationalMatrix(ContractModel):
    matrix_schema_version: Literal["1"] = "1"
    domain: Literal["QQ"] = "QQ"
    entries: tuple[tuple[CanonicalRational, ...], ...] = Field(
        min_length=1,
        max_length=32,
    )

    @model_validator(mode="after")
    def require_rectangular_nonempty_rows(self) -> Self:
        column_count = len(self.entries[0])
        if column_count == 0 or column_count > 32:
            raise ValueError("matrix rows must contain between 1 and 32 entries")
        if any(len(row) != column_count for row in self.entries):
            raise ValueError("matrix rows must all have the same length")
        return self


class MatrixDeterminantRequest(ContractModel):
    matrix: ExactRationalMatrix

    @model_validator(mode="after")
    def require_square_matrix(self) -> Self:
        if len(self.matrix.entries) != len(self.matrix.entries[0]):
            raise ValueError("determinant computation requires a square matrix")
        return self


class MatrixRankRequest(ContractModel):
    matrix: ExactRationalMatrix


class MatrixDeterminantArtifact(ContractModel):
    result_schema_version: Literal["1"] = "1"
    matrix_uri: ArtifactUri
    determinant: CanonicalRational
    method: Literal["FRACTION_FREE_BAREISS"] = "FRACTION_FREE_BAREISS"


class MatrixRankArtifact(ContractModel):
    result_schema_version: Literal["1"] = "1"
    matrix_uri: ArtifactUri
    rank: int = Field(ge=0, le=32)
    pivot_columns: tuple[int, ...] = Field(max_length=32)
    method: Literal["EXACT_RATIONAL_ROW_REDUCTION"] = "EXACT_RATIONAL_ROW_REDUCTION"


class MatrixDeterminantOutput(ContractModel):
    matrix_uri: ArtifactUri
    determinant_uri: ArtifactUri
    determinant: CanonicalRational
    exactness: Literal["EXACT_RATIONAL"] = "EXACT_RATIONAL"
    determinism: Literal["DETERMINISTIC"] = "DETERMINISTIC"
    verification: Literal["UNVERIFIED"] = "UNVERIFIED"
    certificate_available: Literal[False] = False
    method: Literal["FRACTION_FREE_BAREISS"] = "FRACTION_FREE_BAREISS"


class MatrixRankOutput(ContractModel):
    matrix_uri: ArtifactUri
    rank_uri: ArtifactUri
    rank: int = Field(ge=0, le=32)
    pivot_columns: tuple[int, ...] = Field(max_length=32)
    exactness: Literal["EXACT_RATIONAL"] = "EXACT_RATIONAL"
    determinism: Literal["DETERMINISTIC"] = "DETERMINISTIC"
    verification: Literal["UNVERIFIED"] = "UNVERIFIED"
    certificate_available: Literal[False] = False
    method: Literal["EXACT_RATIONAL_ROW_REDUCTION"] = "EXACT_RATIONAL_ROW_REDUCTION"
