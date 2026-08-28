"""Domain adapter for combinatorial-matrix operations."""

from __future__ import annotations

from jacobian.math.combinatorial_matrices._models import (
    DeterminantProfileRequest,
    DeterminantProfileResult,
    GramProfileRequest,
    GramProfileResult,
    NormalizeRequest,
    NormalizeResult,
    SignProfileRequest,
    SignProfileResult,
    SylvesterRequest,
    SylvesterResult,
)
from jacobian.math.combinatorial_matrices.operations import (
    determinant_profile,
    gram_profile,
    normalize,
    sign_profile,
    sylvester,
)
from jacobian.math.combinatorial_matrices.values import HadamardMatrix, SignMatrix

__all__ = [
    "compute_determinant_profile",
    "compute_gram_profile",
    "compute_normalize",
    "compute_sign_profile",
    "compute_sylvester",
]


def compute_sign_profile(request: SignProfileRequest) -> SignProfileResult:
    result = sign_profile(request.matrix)
    return SignProfileResult(
        row_count=result["row_count"],
        column_count=result["column_count"],
        plus_one_count=result["plus_one_count"],
        minus_one_count=result["minus_one_count"],
        row_sums=result["row_sums"],
        column_sums=result["column_sums"],
        is_square=result["is_square"],
    )


def compute_gram_profile(request: GramProfileRequest) -> GramProfileResult:
    result = gram_profile(request.matrix)
    return GramProfileResult(
        order=result["order"],
        gram=result["gram"],
        diagonal_residuals=result["diagonal_residuals"],
        nonzero_off_diagonal=result["nonzero_off_diagonal"],
        is_hadamard=result["is_hadamard"],
    )


def compute_normalize(request: NormalizeRequest) -> NormalizeResult:
    result = normalize(request.matrix)
    rows = result["normalized"]
    value_type = (
        HadamardMatrix if isinstance(request.matrix, HadamardMatrix) else SignMatrix
    )
    normalized = value_type(rows=rows)
    return NormalizeResult(
        normalized=normalized,
        row_switches=result["row_switches"],
        column_switches=result["column_switches"],
    )


def compute_determinant_profile(
    request: DeterminantProfileRequest,
) -> DeterminantProfileResult:
    result = determinant_profile(request.matrix)
    return DeterminantProfileResult(
        order=result["order"],
        determinant_magnitude=result["determinant_magnitude"],
        gram_determinant=result["gram_determinant"],
        identity=result["identity"],
    )


def compute_sylvester(request: SylvesterRequest) -> SylvesterResult:
    result = sylvester(request.k)
    return SylvesterResult(
        matrix=HadamardMatrix(rows=result["matrix"]),
        construction=result["construction"],
        order=result["order"],
    )
