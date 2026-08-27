"""Typed contracts for prime-coverage profiles."""

from __future__ import annotations

from pydantic import Field, model_validator
from typing import Self

from jacobian._models import StrictModel

MAX_COVERAGE_UPPER: int = 10_000_000
MAX_COVERAGE_WIDTH: int = 1_000_000


class PrimeCoverageProfileRequest(StrictModel):
    """A bounded closed interval [L, U] for prime-coverage profiling."""

    lower_bound: int = Field(ge=1, le=MAX_COVERAGE_UPPER)
    upper_bound: int = Field(ge=1, le=MAX_COVERAGE_UPPER)

    @model_validator(mode="after")
    def require_valid_interval(self) -> Self:
        if self.upper_bound < self.lower_bound:
            raise ValueError("upper_bound must be >= lower_bound")
        if self.upper_bound - self.lower_bound + 1 > MAX_COVERAGE_WIDTH:
            raise ValueError("interval width exceeds maximum supported width")
        return self


class PrimeCoverageProfileRow(StrictModel):
    """One (n, omega(n)) pair where omega(n) is the number of distinct prime factors."""

    n: int
    distinct_prime_count: int = Field(ge=0)


class PrimeCoverageProfileResult(StrictModel):
    """Complete ordered prime-coverage table over [L, U]."""

    lower_bound: int
    upper_bound: int
    rows: list[PrimeCoverageProfileRow]


__all__ = [
    "PrimeCoverageProfileRequest",
    "PrimeCoverageProfileResult",
    "PrimeCoverageProfileRow",
    "MAX_COVERAGE_UPPER",
    "MAX_COVERAGE_WIDTH",
]
