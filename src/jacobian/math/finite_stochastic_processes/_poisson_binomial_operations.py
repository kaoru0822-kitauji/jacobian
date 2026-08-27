"""Exact Poisson-binomial count distribution kernel using rational arithmetic."""

from __future__ import annotations

from fractions import Fraction

from jacobian._exact import CanonicalRational
from jacobian.math.finite_stochastic_processes._poisson_binomial_models import (
    PoissonBinomialRequest,
    PoissonBinomialResult,
)
from jacobian.math.finite_stochastic_processes.operations import poisson_binomial


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
    probs = tuple(
        CanonicalRational.from_fraction(Fraction(p)) for p in request.probabilities
    )
    return PoissonBinomialResult(
        probabilities=probs,
        count_distribution=poisson_binomial(probs),
    )


__all__ = ["compute_poisson_binomial"]
