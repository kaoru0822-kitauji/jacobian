"""Named Pydantic wire contracts for exact arithmetic capabilities.

The arithmetic domain owns integer absolute value, sign, decimal digit
sum/count, base expansion, integer nth root, and rational arithmetic/order.
Number-theory contracts (gcd, lcm, divisibility, primes, modular arithmetic,
integer predicates) live in ``contracts/number_theory.py``.
"""

from __future__ import annotations

from fractions import Fraction
from math import isqrt
from typing import Annotated, Literal, Self

from pydantic import Field, StrictInt, StringConstraints, model_validator

from jacobian.contracts.exact import (
    CanonicalInteger,
    CanonicalRational,
    require_bounded_rational,
)
from jacobian.contracts.results import ContractModel

# ---------------------------------------------------------------------------
# Shared bounds
# ---------------------------------------------------------------------------

_MAX_BASE = 10_000
_MAX_NONNEGATIVE = 1_000
MAX_BASE_DIGITS = 1_024
MAX_REAL_QUADRATIC_RADICAND = 1_000_000
MAX_REAL_QUADRATIC_DIGITS = 256

# A positional digit is a small non-negative canonical integer string.  The
# max length of 4 comfortably covers every base up to ``_MAX_BASE`` (10_000).
BaseDigit = Annotated[
    str,
    StringConstraints(
        pattern=r"^(?:0|[1-9][0-9]*)$",
        max_length=4,
        strict=True,
    ),
]


# ---------------------------------------------------------------------------
# Requests — unary integer
# ---------------------------------------------------------------------------


class IntegerValueRequest(ContractModel):
    """One canonical integer supplied to a unary integer operation."""

    value: CanonicalInteger


# ---------------------------------------------------------------------------
# Requests — base expansion
# ---------------------------------------------------------------------------


class IntegerBaseDigitsRequest(ContractModel):
    """Expand one integer's absolute value in a positional base.

    The positional base is named explicitly so this request cannot be confused
    with modular arithmetic.
    """

    value: CanonicalInteger
    base: int = Field(ge=2, le=_MAX_BASE)


# ---------------------------------------------------------------------------
# Requests — nth root
# ---------------------------------------------------------------------------


class IntegerNthRootRequest(ContractModel):
    """One non-negative integer and a positive root degree."""

    value: int = Field(ge=0, le=_MAX_NONNEGATIVE)
    degree: int = Field(ge=1, le=_MAX_NONNEGATIVE)


# ---------------------------------------------------------------------------
# Requests — real quadratic order
# ---------------------------------------------------------------------------


def _is_square_free(value: int) -> bool:
    for divisor in range(2, isqrt(value) + 1):
        if value % (divisor * divisor) == 0:
            return False
    return True


def _fraction_order(left: Fraction, right: Fraction) -> Literal["LT", "EQ", "GT"]:
    if left < right:
        return "LT"
    if left > right:
        return "GT"
    return "EQ"


def _quadratic_sign(
    rational_part: Fraction,
    radical_coefficient: Fraction,
    radicand: int,
) -> Literal[-1, 0, 1]:
    if radical_coefficient == 0:
        if rational_part < 0:
            return -1
        if rational_part > 0:
            return 1
        return 0
    if rational_part == 0:
        return -1 if radical_coefficient < 0 else 1
    if (rational_part > 0) == (radical_coefficient > 0):
        return -1 if rational_part < 0 else 1
    rational_square = rational_part * rational_part
    radical_square = radical_coefficient * radical_coefficient * radicand
    if rational_square == radical_square:
        raise ValueError("square-free quadratic magnitudes cannot tie")
    dominant = (
        radical_coefficient if radical_square > rational_square else rational_part
    )
    return -1 if dominant < 0 else 1


class RealQuadraticValue(ContractModel):
    """One canonical real value ``a + b*sqrt(d)`` with square-free ``d``."""

    rational_part: CanonicalRational
    radical_coefficient: CanonicalRational
    radicand: StrictInt = Field(ge=2, le=MAX_REAL_QUADRATIC_RADICAND)

    @model_validator(mode="after")
    def require_bounded_canonical_quadratic(self) -> Self:
        require_bounded_rational(
            self.rational_part,
            max_digits=MAX_REAL_QUADRATIC_DIGITS,
            label="real-quadratic rational part",
        )
        require_bounded_rational(
            self.radical_coefficient,
            max_digits=MAX_REAL_QUADRATIC_DIGITS,
            label="real-quadratic radical coefficient",
        )
        if not _is_square_free(self.radicand):
            raise ValueError("real-quadratic radicand must be square-free")
        return self


class RealQuadraticOrderRequest(ContractModel):
    """Two values in one explicitly shared real quadratic field."""

    left: RealQuadraticValue
    right: RealQuadraticValue

    @model_validator(mode="after")
    def require_shared_radicand(self) -> Self:
        if self.left.radicand != self.right.radicand:
            raise ValueError("real-quadratic comparison requires one shared radicand")
        return self


# ---------------------------------------------------------------------------
# Structured results — integer
# ---------------------------------------------------------------------------


class IntegerValueResult(ContractModel):
    """One canonical integer produced by a unary integer operation."""

    value: CanonicalInteger


class IntegerSignResult(ContractModel):
    """The sign of one integer as -1, 0, or 1."""

    sign: Literal[-1, 0, 1]


class IntegerNthRootResult(ContractModel):
    """The floor nth root of one integer and whether it is exact."""

    root: CanonicalInteger
    exact: bool


class IntegerBaseDigitsResult(ContractModel):
    """One integer's sign and positional digits in a declared base."""

    sign: Literal[-1, 0, 1]
    base: int = Field(ge=2, le=_MAX_BASE)
    digits: tuple[BaseDigit, ...] = Field(min_length=1, max_length=MAX_BASE_DIGITS)

    @model_validator(mode="after")
    def require_canonical_digits(self) -> Self:
        if any(int(digit) >= self.base for digit in self.digits):
            raise ValueError("every positional digit must be smaller than the base")
        if self.sign == 0 and self.digits != ("0",):
            raise ValueError("zero sign requires the canonical zero digit")
        if self.sign != 0 and self.digits[0] == "0":
            raise ValueError("nonzero positional digits cannot have a leading zero")
        return self


# ---------------------------------------------------------------------------
# Structured results — real quadratic order
# ---------------------------------------------------------------------------


class RealQuadraticSignCertificate(ContractModel):
    rational_part_squared: CanonicalRational
    radical_part_squared: CanonicalRational
    magnitude_order: Literal["LT", "EQ", "GT"]


class RealQuadraticOrderResult(ContractModel):
    """Exact order and inspectable sign data for two real quadratic values."""

    result_schema_version: Literal["1"] = "1"
    left: RealQuadraticValue
    right: RealQuadraticValue
    difference: RealQuadraticValue
    order: Literal["LT", "EQ", "GT"]
    sign_basis: Literal[
        "RATIONAL_ONLY",
        "RADICAL_ONLY",
        "SAME_SIGN",
        "OPPOSING_SIGNS_SQUARED_MAGNITUDES",
    ]
    sign_certificate: RealQuadraticSignCertificate
    arithmetic: Literal["EXACT_REAL_QUADRATIC"] = "EXACT_REAL_QUADRATIC"

    @model_validator(mode="after")
    def bind_exact_order(self) -> Self:
        if not (self.left.radicand == self.right.radicand == self.difference.radicand):
            raise ValueError("result values must share one radicand")
        left_a = self.left.rational_part.as_fraction()
        left_b = self.left.radical_coefficient.as_fraction()
        right_a = self.right.rational_part.as_fraction()
        right_b = self.right.radical_coefficient.as_fraction()
        difference_a = left_a - right_a
        difference_b = left_b - right_b
        if (
            self.difference.rational_part.as_fraction() != difference_a
            or self.difference.radical_coefficient.as_fraction() != difference_b
        ):
            raise ValueError("result difference must equal left minus right")
        sign = _quadratic_sign(difference_a, difference_b, self.difference.radicand)
        expected_order: Literal["LT", "EQ", "GT"] = (
            "LT" if sign < 0 else "GT" if sign > 0 else "EQ"
        )
        if self.order != expected_order:
            raise ValueError("result order must match the exact quadratic difference")
        expected_basis = (
            "RATIONAL_ONLY"
            if difference_b == 0
            else "RADICAL_ONLY"
            if difference_a == 0
            else "SAME_SIGN"
            if (difference_a > 0) == (difference_b > 0)
            else "OPPOSING_SIGNS_SQUARED_MAGNITUDES"
        )
        if self.sign_basis != expected_basis:
            raise ValueError("sign basis must match the exact difference structure")
        rational_square = difference_a * difference_a
        radical_square = difference_b * difference_b * self.difference.radicand
        if (
            self.sign_certificate.rational_part_squared.as_fraction() != rational_square
            or self.sign_certificate.radical_part_squared.as_fraction()
            != radical_square
            or self.sign_certificate.magnitude_order
            != _fraction_order(rational_square, radical_square)
        ):
            raise ValueError("sign certificate must contain exact squared magnitudes")
        return self
