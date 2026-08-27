"""Exact p-adic valuation profiles of binomial coefficients via Kummer's theorem."""

from __future__ import annotations

from jacobian.catalog.models import OperationDomainValidationError
from jacobian.math.number_theory._binomial_valuation_models import (
    _MAX_BINOMIAL_ROWS_FROM_OUTPUT,
    MAX_BINOMIAL_DIGIT_WORK,
    MAX_BINOMIAL_PROFILE_RESULT_BYTES,
    BinomialValuationProfileRequest,
    BinomialValuationProfileResult,
    BinomialValuationProfileRow,
    _base_digit_count,
    _binomial_result_upper_bound_bytes,
)


def _reject(code: str, message: str, *location: str) -> None:
    raise OperationDomainValidationError(
        location=location,
        code=f"number_theory.{code}",
        message=message,
    )


def _admit_binomial_profile(request: BinomialValuationProfileRequest) -> None:
    if request.n + 1 > _MAX_BINOMIAL_ROWS_FROM_OUTPUT:
        _reject(
            "binomial_profile_output_exceeded",
            "valuation profile exceeds the canonical output budget",
            "n",
        )
    predicted = _binomial_result_upper_bound_bytes(request.n, request.prime)
    if predicted > MAX_BINOMIAL_PROFILE_RESULT_BYTES:
        _reject(
            "binomial_profile_output_exceeded",
            "valuation profile exceeds the canonical output budget of "
            f"{MAX_BINOMIAL_PROFILE_RESULT_BYTES} bytes",
            "n",
        )
    digit_work = (request.n + 1) * max(1, _base_digit_count(request.n, request.prime))
    if digit_work > MAX_BINOMIAL_DIGIT_WORK:
        _reject(
            "binomial_profile_work_exceeded",
            "valuation profile exceeds the digitwise work budget of "
            f"{MAX_BINOMIAL_DIGIT_WORK} steps",
            "n",
        )
    from sympy import isprime

    if not isprime(request.prime):
        _reject(
            "binomial_profile_base_not_prime",
            "prime must be a prime number",
            "prime",
        )


def _count_carries(n: int, k: int, p: int) -> int:
    """Count carries when adding k and (n-k) in base p (Kummer's theorem)."""
    a = k
    b = n - k
    carries = 0
    carry = 0
    while a > 0 or b > 0 or carry > 0:
        da = a % p
        db = b % p
        s = da + db + carry
        if s >= p:
            carries += 1
            carry = 1
        else:
            carry = 0
        a //= p
        b //= p
    return carries


def compute_binomial_valuation_profile(
    request: BinomialValuationProfileRequest,
) -> BinomialValuationProfileResult:
    """Compute v_p(C(n,k)) for all k from 0 to n using Kummer's theorem.

    v_p(C(n,k)) = number of carries when adding k and (n-k) in base p.
    """
    _admit_binomial_profile(request)
    n = request.n
    p = request.prime
    rows = []
    for k in range(n + 1):
        valuation = _count_carries(n, k, p)
        rows.append(BinomialValuationProfileRow(k=k, valuation=valuation))
    return BinomialValuationProfileResult(n=n, prime=p, rows=rows)


__all__ = ["compute_binomial_valuation_profile"]
