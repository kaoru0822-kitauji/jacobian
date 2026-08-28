"""Contracts owned by the derived integer kernels."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, StrictInt, model_validator

from jacobian._models import StrictModel
from jacobian.math.number_theory._models import _validation_error

MAX_FACTORIAL_ARGUMENT = 100_000
MAX_FACTORIAL_BASE = 1_000_000
MAX_FLOOR_SQUARE_ROOT = 1_000_000
MAX_LEGENDRE_PRIME = 10_000_000


class FloorSquareRootRequest(StrictModel):
    n: StrictInt = Field(ge=0, le=MAX_FLOOR_SQUARE_ROOT**2)


class FloorSquareRootResult(StrictModel):
    """The exact floor of the nonnegative integer square root."""

    root: StrictInt = Field(ge=0, le=MAX_FLOOR_SQUARE_ROOT)


def _is_bounded_prime(value: int) -> bool:
    """Decide primality within the Legendre-denominator admission envelope."""

    if value < 2:
        return False
    if value in (2, 3):
        return True
    if value % 2 == 0 or value % 3 == 0:
        return False
    candidate = 5
    while candidate * candidate <= value:
        if value % candidate == 0 or value % (candidate + 2) == 0:
            return False
        candidate += 6
    return True


class LegendreSymbolRequest(StrictModel):
    """Arguments for the Legendre symbol with a bounded odd prime denominator."""

    a: StrictInt = Field(ge=-(2**53 - 1), le=2**53 - 1)
    prime: StrictInt = Field(ge=3, le=MAX_LEGENDRE_PRIME)

    @model_validator(mode="after")
    def require_prime_denominator(self) -> Self:
        if not _is_bounded_prime(self.prime):
            raise _validation_error(
                "legendre_denominator_must_be_prime",
                "Legendre denominator must be prime",
            )
        return self


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
