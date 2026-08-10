"""Exact order for bounded values in one real quadratic field."""

from __future__ import annotations

from fractions import Fraction
from typing import Literal

from sympy import Rational, sign, sqrt

from jacobian.contracts.arithmetic import (
    RealQuadraticOrderRequest,
    RealQuadraticOrderResult,
    RealQuadraticSignCertificate,
    RealQuadraticValue,
)
from jacobian.contracts.exact import CanonicalRational
from jacobian.domains._examples import example
from jacobian.domains.arithmetic._support import arithmetic_operation


def _wire_rational(value: Fraction) -> CanonicalRational:
    return CanonicalRational.from_fraction(value)


def _wire_value(
    rational_part: Fraction,
    radical_coefficient: Fraction,
    radicand: int,
) -> RealQuadraticValue:
    return RealQuadraticValue(
        rational_part=_wire_rational(rational_part),
        radical_coefficient=_wire_rational(radical_coefficient),
        radicand=radicand,
    )


def _magnitude_order(left: Fraction, right: Fraction) -> Literal["LT", "EQ", "GT"]:
    if left < right:
        return "LT"
    if left > right:
        return "GT"
    return "EQ"


def compute_real_quadratic_order(
    request: RealQuadraticOrderRequest,
) -> RealQuadraticOrderResult:
    """Compare two ``a + b*sqrt(d)`` values using exact SymPy ordering."""

    left_a = request.left.rational_part.as_fraction()
    left_b = request.left.radical_coefficient.as_fraction()
    right_a = request.right.rational_part.as_fraction()
    right_b = request.right.radical_coefficient.as_fraction()
    difference_a = left_a - right_a
    difference_b = left_b - right_b
    radicand = request.left.radicand
    expression = Rational(difference_a.numerator, difference_a.denominator) + Rational(
        difference_b.numerator, difference_b.denominator
    ) * sqrt(radicand)
    exact_sign = int(sign(expression))
    if exact_sign not in {-1, 0, 1}:
        raise ValueError("SymPy did not determine the exact real-quadratic sign")
    order: Literal["LT", "EQ", "GT"] = (
        "LT" if exact_sign < 0 else "GT" if exact_sign > 0 else "EQ"
    )
    sign_basis: Literal[
        "RATIONAL_ONLY",
        "RADICAL_ONLY",
        "SAME_SIGN",
        "OPPOSING_SIGNS_SQUARED_MAGNITUDES",
    ] = (
        "RATIONAL_ONLY"
        if difference_b == 0
        else "RADICAL_ONLY"
        if difference_a == 0
        else "SAME_SIGN"
        if (difference_a > 0) == (difference_b > 0)
        else "OPPOSING_SIGNS_SQUARED_MAGNITUDES"
    )
    rational_square = difference_a * difference_a
    radical_square = difference_b * difference_b * radicand
    return RealQuadraticOrderResult(
        left=request.left,
        right=request.right,
        difference=_wire_value(difference_a, difference_b, radicand),
        order=order,
        sign_basis=sign_basis,
        sign_certificate=RealQuadraticSignCertificate(
            rational_part_squared=_wire_rational(rational_square),
            radical_part_squared=_wire_rational(radical_square),
            magnitude_order=_magnitude_order(rational_square, radical_square),
        ),
    )


REAL_QUADRATIC_CAPABILITIES = (
    arithmetic_operation(
        "arithmetic.real_quadratic.order.compute",
        "Compare exact real quadratic values",
        (
            "Compute the exact order of two bounded canonical values a+b*sqrt(d) "
            "with one shared positive square-free radicand, retaining their exact "
            "difference and squared-magnitude sign certificate."
        ),
        RealQuadraticOrderRequest,
        RealQuadraticOrderResult,
        compute_real_quadratic_order,
        "arithmetic",
        "real-quadratic",
        "quadratic-surd",
        "exact-order",
        invocation_examples=(
            example(
                "pang_m4_matrix_young_gap",
                "Compare 3*sqrt(3)/8 with 1/2+sqrt(3)/20 exactly.",
                {
                    "left": {
                        "rational_part": {"num": "0", "den": "1"},
                        "radical_coefficient": {"num": "3", "den": "8"},
                        "radicand": 3,
                    },
                    "right": {
                        "rational_part": {"num": "1", "den": "2"},
                        "radical_coefficient": {"num": "1", "den": "20"},
                        "radicand": 3,
                    },
                },
            ),
        ),
    ),
)


__all__ = ["REAL_QUADRATIC_CAPABILITIES", "compute_real_quadratic_order"]
