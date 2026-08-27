"""Tests for prime-coverage and binomial-valuation profiles."""

from jacobian.math.number_theory._binomial_valuation_models import (
    BinomialValuationProfileRequest,
)
from jacobian.math.number_theory._binomial_valuation_operations import (
    compute_binomial_valuation_profile,
)
from jacobian.math.number_theory._prime_coverage_models import (
    PrimeCoverageProfileRequest,
)
from jacobian.math.number_theory._prime_coverage_operations import (
    compute_prime_coverage_profile,
)


def test_prime_coverage_small() -> None:
    result = compute_prime_coverage_profile(
        PrimeCoverageProfileRequest(lower_bound=1, upper_bound=10)
    )
    counts = [r.distinct_prime_count for r in result.rows]
    # omega(1)=0, omega(2)=1, omega(3)=1, omega(4)=1, omega(5)=1, omega(6)=2, omega(7)=1, omega(8)=1, omega(9)=1, omega(10)=2
    assert counts == [0, 1, 1, 1, 1, 2, 1, 1, 1, 2]


def test_prime_coverage_primes() -> None:
    result = compute_prime_coverage_profile(
        PrimeCoverageProfileRequest(lower_bound=2, upper_bound=50)
    )
    for row in result.rows:
        from sympy import isprime

        if isprime(row.n):
            assert row.distinct_prime_count == 1


def test_binomial_valuation_basic() -> None:
    # v_2(C(4,2)) = v_2(6) = 1
    result = compute_binomial_valuation_profile(
        BinomialValuationProfileRequest(n=4, prime=2)
    )
    assert result.rows[2].valuation == 1


def test_binomial_valuation_kummer() -> None:
    # v_2(C(10,3)) = v_2(120) = 3
    result = compute_binomial_valuation_profile(
        BinomialValuationProfileRequest(n=10, prime=2)
    )
    assert result.rows[3].valuation == 3
    # v_2(C(10,5)) = v_2(252) = 2
    assert result.rows[5].valuation == 2


def test_binomial_valuation_matches_sympy() -> None:
    from sympy import binomial

    result = compute_binomial_valuation_profile(
        BinomialValuationProfileRequest(n=8, prime=3)
    )
    for row in result.rows:
        val = int(binomial(8, row.k))
        # Count factor of 3 in val
        expected = 0
        temp = val
        while temp % 3 == 0:
            expected += 1
            temp //= 3
        assert row.valuation == expected
