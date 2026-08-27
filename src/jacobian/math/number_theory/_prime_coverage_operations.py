"""Exact prime-coverage profile kernel."""

from __future__ import annotations

import math

from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.number_theory._prime_coverage_models import (
    MAX_COVERAGE_RESULT_BYTES,
    MAX_COVERAGE_WORK,
    PrimeCoverageProfileRequest,
    PrimeCoverageProfileResult,
    PrimeCoverageProfileRow,
    _coverage_result_upper_bound_bytes,
    _coverage_work_upper_bound,
)


def _reject(code: str, message: str, *location: str) -> None:
    raise OperationDomainValidationError(
        location=location,
        code=f"number_theory.{code}",
        message=message,
    )


def _admit_prime_coverage(request: PrimeCoverageProfileRequest) -> None:
    if request.upper_bound < request.lower_bound:
        _reject(
            "prime_coverage_interval_reversed",
            "upper_bound must be >= lower_bound",
            "upper_bound",
        )
    predicted = _coverage_result_upper_bound_bytes(
        request.lower_bound, request.upper_bound
    )
    if predicted > MAX_COVERAGE_RESULT_BYTES:
        _reject(
            "prime_coverage_output_exceeded",
            "interval result exceeds the canonical output budget of "
            f"{MAX_COVERAGE_RESULT_BYTES} bytes",
            "lower_bound",
            "upper_bound",
        )
    work = _coverage_work_upper_bound(request.lower_bound, request.upper_bound)
    if work > MAX_COVERAGE_WORK:
        _reject(
            "prime_coverage_work_exceeded",
            "interval exceeds the segmented prime-coverage work budget of "
            f"{MAX_COVERAGE_WORK} steps",
            "lower_bound",
            "upper_bound",
        )


def _simple_sieve(limit: int) -> list[int]:
    if limit < 2:
        return []
    is_prime = bytearray(b"\x01") * (limit + 1)
    is_prime[0] = is_prime[1] = 0
    for i in range(2, math.isqrt(limit) + 1):
        if is_prime[i]:
            for j in range(i * i, limit + 1, i):
                is_prime[j] = 0
    return [i for i in range(2, limit + 1) if is_prime[i]]


def _segmented_omega(lower_bound: int, upper_bound: int) -> list[int]:
    """Return omega for one interval using a square-root base sieve."""

    width = upper_bound - lower_bound + 1
    residuals = list(range(lower_bound, upper_bound + 1))
    counts = bytearray(width)
    for prime in _simple_sieve(math.isqrt(upper_bound)):
        first = max(
            prime * prime,
            ((lower_bound + prime - 1) // prime) * prime,
        )
        for multiple in range(first, upper_bound + 1, prime):
            index = multiple - lower_bound
            residual = residuals[index]
            if residual % prime:
                continue
            counts[index] += 1
            while residual % prime == 0:
                residual //= prime
            residuals[index] = residual
    for index, residual in enumerate(residuals):
        if residual > 1:
            counts[index] += 1
    return list(counts)


def compute_prime_coverage_profile(
    request: PrimeCoverageProfileRequest,
) -> PrimeCoverageProfileResult:
    """Compute omega(n) (distinct prime factor count) for every n in [L, U]."""
    _admit_prime_coverage(request)
    lo = request.lower_bound
    hi = request.upper_bound
    omegas = _segmented_omega(lo, hi)
    rows = []
    for n, omega in zip(range(lo, hi + 1), omegas, strict=True):
        rows.append(PrimeCoverageProfileRow(n=n, distinct_prime_count=omega))
    return PrimeCoverageProfileResult(lower_bound=lo, upper_bound=hi, rows=rows)


__all__ = ["compute_prime_coverage_profile"]
