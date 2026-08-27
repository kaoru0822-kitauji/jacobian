"""Exact prime-coverage profile kernel."""

from __future__ import annotations

import math

from jacobian.math.number_theory._prime_coverage_models import (
    PrimeCoverageProfileRequest,
    PrimeCoverageProfileResult,
    PrimeCoverageProfileRow,
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


def compute_prime_coverage_profile(
    request: PrimeCoverageProfileRequest,
) -> PrimeCoverageProfileResult:
    """Compute omega(n) (distinct prime factor count) for every n in [L, U]."""
    lo = request.lower_bound
    hi = request.upper_bound
    primes = _simple_sieve(hi)
    rows = []
    for n in range(lo, hi + 1):
        if n == 1:
            rows.append(PrimeCoverageProfileRow(n=1, distinct_prime_count=0))
            continue
        m = n
        omega = 0
        for p in primes:
            if p * p > m:
                break
            if m % p == 0:
                omega += 1
                while m % p == 0:
                    m //= p
        if m > 1:
            omega += 1
        rows.append(PrimeCoverageProfileRow(n=n, distinct_prime_count=omega))
    return PrimeCoverageProfileResult(lower_bound=lo, upper_bound=hi, rows=rows)


__all__ = ["compute_prime_coverage_profile"]
