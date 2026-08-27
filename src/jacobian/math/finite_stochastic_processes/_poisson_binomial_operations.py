"""Exact Poisson-binomial count distribution kernel using rational arithmetic."""

from __future__ import annotations

from jacobian.math.finite_stochastic_processes._poisson_binomial_models import (
    PoissonBinomialRequest,
    PoissonBinomialResult,
)
from jacobian.math.finite_stochastic_processes.operations import (
    _poisson_binomial_kernel,
)


def compute_poisson_binomial(
    request: PoissonBinomialRequest,
) -> PoissonBinomialResult:
    """Compute the exact Poisson-binomial count distribution.

    Given independent Bernoulli trials with success probabilities
    p_1, ..., p_n (as canonical rationals), the Poisson-binomial
    distribution gives the probability of exactly k successes for k = 0, ..., n.

    Uses the direct recurrence with exact rational arithmetic:
    P(k, n) = P(k, n-1) * (1-p_n) + P(k-1, n-1) * p_n
    """
    return PoissonBinomialResult._from_kernel(
        request,
        count_distribution=_poisson_binomial_kernel(request.admission_plan),
    )


__all__ = ["compute_poisson_binomial"]
