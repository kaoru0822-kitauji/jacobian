"""Exact arithmetic on Python integers and fractions."""

from fractions import Fraction
from typing import SupportsIndex

__all__ = ["absolute_value", "quotient", "reciprocal", "sign", "sum_rationals"]


def absolute_value(value: SupportsIndex) -> int:
    """Return the exact absolute value of an integer-like value."""

    return abs(value.__index__())


def sign(value: SupportsIndex) -> int:
    """Return -1, 0, or 1 according to the sign of an integer."""

    integer = value.__index__()
    return (integer > 0) - (integer < 0)


def reciprocal(value: Fraction | int) -> Fraction:
    """Return the exact reciprocal, rejecting zero."""

    rational = Fraction(value)
    if not rational:
        raise ZeroDivisionError("zero has no reciprocal")
    return 1 / rational


def sum_rationals(left: Fraction | int, right: Fraction | int) -> Fraction:
    """Add two exact rational values."""

    return Fraction(left) + Fraction(right)


def quotient(left: Fraction | int, right: Fraction | int) -> Fraction:
    """Divide two exact rational values."""

    divisor = Fraction(right)
    if not divisor:
        raise ZeroDivisionError("division by zero")
    return Fraction(left) / divisor
