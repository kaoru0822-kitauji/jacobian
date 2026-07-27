"""Exact polynomial invariant capabilities."""

from jacobian.contracts.polynomial_operations import (
    PolynomialDiscriminantRequest,
    PolynomialDiscriminantResult,
    PolynomialGcdRequest,
    PolynomialGcdResult,
    PolynomialResultantRequest,
    PolynomialResultantResult,
    PolynomialSquareFreeDecompositionResult,
    PolynomialSquareFreeRequest,
)
from jacobian.domains.polynomial._support import polynomial_operation
from jacobian.domains.polynomial.operations import (
    polynomial_discriminant,
    polynomial_gcd,
    polynomial_resultant,
    polynomial_square_free_decomposition,
)

POLYNOMIAL_INVARIANT_CAPABILITIES = (
    polynomial_operation(
        "polynomial.compute.gcd",
        "Compute a polynomial GCD and Bézout identity",
        "Compute the monic GCD of two bounded univariate polynomials over QQ.",
        PolynomialGcdRequest,
        PolynomialGcdResult,
        polynomial_gcd,
        "polynomial",
        "gcd",
        "bezout",
    ),
    polynomial_operation(
        "polynomial.compute.resultant",
        "Compute a polynomial resultant",
        "Compute the exact resultant in one named elimination variable over QQ.",
        PolynomialResultantRequest,
        PolynomialResultantResult,
        polynomial_resultant,
        "polynomial",
        "resultant",
        "elimination",
    ),
    polynomial_operation(
        "polynomial.compute.discriminant",
        "Compute a polynomial discriminant",
        "Compute the standard exact discriminant in one named variable over QQ.",
        PolynomialDiscriminantRequest,
        PolynomialDiscriminantResult,
        polynomial_discriminant,
        "polynomial",
        "discriminant",
    ),
    polynomial_operation(
        "polynomial.compute.square_free_decomposition",
        "Compute a square-free decomposition",
        "Decompose a bounded polynomial over QQ into monic square-free factors.",
        PolynomialSquareFreeRequest,
        PolynomialSquareFreeDecompositionResult,
        polynomial_square_free_decomposition,
        "polynomial",
        "square-free",
        "multiplicity",
    ),
)

__all__ = ["POLYNOMIAL_INVARIANT_CAPABILITIES"]
