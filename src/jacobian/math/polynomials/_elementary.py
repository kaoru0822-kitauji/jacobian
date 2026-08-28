"""Domain-owned elementary integer and rational polynomial operations."""

from jacobian.catalog._examples import example
from jacobian.math.polynomials._elementary_operations import (
    integer_polynomial_gcd,
)
from jacobian.math.polynomials._models import (
    IntegerPolynomialGcdResult,
    IntegerPolynomialPairRequest,
)
from jacobian.math.polynomials._support import polynomial_operation

INTEGER_POLYNOMIAL_OPERATIONS = (
    polynomial_operation(
        "polynomial.integer.compute.gcd",
        "Compute an integer-polynomial GCD",
        (
            "Compute the nonnegative-leading GCD in ZZ[x], including the content "
            "of both inputs and the result."
        ),
        IntegerPolynomialPairRequest,
        IntegerPolynomialGcdResult,
        integer_polynomial_gcd,
        "polynomial",
        "integer",
        "gcd",
        examples=(
            example(
                "integer_gcd",
                "Compute the GCD of two integer polynomials.",
                {
                    "left": {"coefficients": ["6", "6", "0"]},
                    "right": {"coefficients": ["8", "8", "0"]},
                },
            ),
        ),
    ),
)

__all__ = ["INTEGER_POLYNOMIAL_OPERATIONS"]
