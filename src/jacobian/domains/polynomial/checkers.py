"""Independent checker declarations owned by the polynomial domain."""

from jacobian.checker_operations import ExactReplayCheckerDeclaration
from jacobian.contracts.polynomial_operations import (
    PolynomialDiscriminantRequest,
    PolynomialGcdRequest,
    PolynomialResultantRequest,
    PolynomialSquareFreeRequest,
)

POLYNOMIAL_EXACT_REPLAY_CHECKERS = (
    ExactReplayCheckerDeclaration(
        "polynomial.compute.gcd",
        PolynomialGcdRequest,
        "check_polynomial_gcd",
        "polynomial.gcd.flint-replay",
    ),
    ExactReplayCheckerDeclaration(
        "polynomial.compute.resultant",
        PolynomialResultantRequest,
        "check_polynomial_resultant",
        "polynomial.resultant.flint-replay",
    ),
    ExactReplayCheckerDeclaration(
        "polynomial.compute.discriminant",
        PolynomialDiscriminantRequest,
        "check_polynomial_discriminant",
        "polynomial.discriminant.flint-replay",
    ),
    ExactReplayCheckerDeclaration(
        "polynomial.compute.square_free_decomposition",
        PolynomialSquareFreeRequest,
        "check_polynomial_square_free",
        "polynomial.square-free.flint-replay",
    ),
)

__all__ = ["POLYNOMIAL_EXACT_REPLAY_CHECKERS"]
