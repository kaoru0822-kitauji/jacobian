"""Typed contracts for prime-coverage profiles."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from jacobian._models import StrictModel
from jacobian.canonical import (
    CanonicalLimits,
    encode_strict_json,
    strict_json_object_size,
)

MAX_COVERAGE_UPPER: int = 10_000_000
MAX_COVERAGE_WIDTH: int = 1_000_000
MAX_COVERAGE_RESULT_BYTES: int = CanonicalLimits().max_output_bytes
_MAX_DISTINCT_PRIME_COUNT = 8


def _json_array_size(item_size: int, count: int) -> int:
    return 2 + max(count - 1, 0) + count * item_size


def _coverage_result_upper_bound_bytes(lower_bound: int, upper_bound: int) -> int:
    """Bound the exact canonical size of one complete coverage result.

    Every emitted ``n`` is at most ``upper_bound`` and the kernel can produce
    at most eight distinct prime factors for values up to ``MAX_COVERAGE_UPPER``.
    The field and array sizes are calculated with the same canonical encoder
    used by the final result boundary, so accepted requests cannot fail only
    during dispatch serialization.
    """

    width = upper_bound - lower_bound + 1
    row_size = strict_json_object_size(
        (
            ("n", len(encode_strict_json(upper_bound))),
            (
                "distinct_prime_count",
                len(encode_strict_json(_MAX_DISTINCT_PRIME_COUNT)),
            ),
        )
    )
    rows_size = _json_array_size(row_size, width)
    return strict_json_object_size(
        (
            ("lower_bound", len(encode_strict_json(lower_bound))),
            ("upper_bound", len(encode_strict_json(upper_bound))),
            ("rows", rows_size),
        )
    )


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
        predicted = _coverage_result_upper_bound_bytes(
            self.lower_bound, self.upper_bound
        )
        if predicted > MAX_COVERAGE_RESULT_BYTES:
            raise ValueError(
                "interval result exceeds the canonical output budget of "
                f"{MAX_COVERAGE_RESULT_BYTES} bytes"
            )
        return self


class PrimeCoverageProfileRow(StrictModel):
    """One (n, omega(n)) pair where omega(n) is the number of distinct prime factors."""

    n: int = Field(ge=1, le=MAX_COVERAGE_UPPER)
    distinct_prime_count: int = Field(ge=0, le=_MAX_DISTINCT_PRIME_COUNT)


class PrimeCoverageProfileResult(StrictModel):
    """Complete ordered prime-coverage table over [L, U]."""

    lower_bound: int
    upper_bound: int
    rows: list[PrimeCoverageProfileRow]


__all__ = [
    "MAX_COVERAGE_RESULT_BYTES",
    "MAX_COVERAGE_UPPER",
    "MAX_COVERAGE_WIDTH",
    "PrimeCoverageProfileRequest",
    "PrimeCoverageProfileResult",
    "PrimeCoverageProfileRow",
]
