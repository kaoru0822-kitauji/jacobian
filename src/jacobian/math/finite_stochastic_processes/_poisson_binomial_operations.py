"""Exact Poisson-binomial count distribution kernel using rational arithmetic."""

from __future__ import annotations

from fractions import Fraction

from jacobian.math.finite_stochastic_processes._poisson_binomial_models import (
    PoissonBinomialRequest,
    PoissonBinomialResult,
)


def compute_poisson_binomial(
    request: PoissonBinomialRequest,
) -> PoissonBinomialResult:
    """Compute the exact Poisson-binomial count distribution.

    Given independent Bernoulli trials with success probabilities
    p_1, ..., p_n (as rational strings "a/b"), the Poisson-binomial
    distribution gives the probability of exactly k successes for k = 0, ..., n.

    Uses the direct recurrence with exact rational arithmetic:
    P(k, n) = P(k, n-1) * (1-p_n) + P(k-1, n-1) * p_n
    """
    probs = [Fraction(p) for p in request.probabilities]
    n = len(probs)

    # dp[k] = P(exactly k successes)
    dp = [Fraction(0)] * (n + 1)
    dp[0] = Fraction(1)

    for i, p in enumerate(probs):
        q = 1 - p
        new_dp = [Fraction(0)] * (n + 1)
        for k in range(i + 2):
            new_dp[k] += dp[k] * q  # failure
            if k > 0:
                new_dp[k] += dp[k - 1] * p  # success
        dp = new_dp

    # Convert results to strings
    result_probs = [str(Fraction(p)) for p in request.probabilities]
    result_dist = [str(d) for d in dp]

    return PoissonBinomialResult(
        probabilities=result_probs,
        count_distribution=result_dist,
    )


__all__ = ["compute_poisson_binomial"]
