"""Contracts owned by the derived integer kernels."""

from __future__ import annotations

from math import isqrt
from typing import Literal

from pydantic import Field, StrictInt

from jacobian._models import StrictModel
from jacobian.math.number_theory._integer_models import MAX_SAFE_INTEGER

MAX_FACTORIAL_ARGUMENT = 100_000
MAX_FACTORIAL_BASE = 1_000_000
MAX_FLOOR_SQUARE_ROOT = isqrt(MAX_SAFE_INTEGER)
MAX_LEGENDRE_PRIME = MAX_SAFE_INTEGER


class FloorSquareRootRequest(StrictModel):
    n: StrictInt = Field(ge=0, le=MAX_SAFE_INTEGER)


class FloorSquareRootResult(StrictModel):
    """The exact floor of the nonnegative integer square root."""

    root: StrictInt = Field(ge=0, le=MAX_FLOOR_SQUARE_ROOT)


class LegendreSymbolRequest(StrictModel):
    """Arguments for the Legendre symbol with a bounded odd prime denominator."""

    a: StrictInt = Field(ge=-MAX_SAFE_INTEGER, le=MAX_SAFE_INTEGER)
    prime: StrictInt = Field(ge=3, le=MAX_LEGENDRE_PRIME)


class LegendreSymbolResult(StrictModel):
    a: StrictInt
    prime: StrictInt = Field(ge=3, le=MAX_LEGENDRE_PRIME)
    symbol: Literal[-1, 0, 1]


class FactorialValuationRequest(StrictModel):
    """Arguments for the largest exponent ``e`` such that ``base**e`` divides ``n!``."""

    n: StrictInt = Field(ge=0, le=MAX_FACTORIAL_ARGUMENT)
    base: StrictInt = Field(ge=2, le=MAX_FACTORIAL_BASE)


class FactorialValuationResult(StrictModel):
    n: StrictInt = Field(ge=0, le=MAX_FACTORIAL_ARGUMENT)
    base: StrictInt = Field(ge=2, le=MAX_FACTORIAL_BASE)
    valuation: StrictInt = Field(ge=0)


__all__ = [
    "FactorialValuationRequest",
    "FactorialValuationResult",
    "FloorSquareRootRequest",
    "FloorSquareRootResult",
    "LegendreSymbolRequest",
    "LegendreSymbolResult",
]
