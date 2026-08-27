"""Tests for exact Poisson-binomial count distributions."""

from jacobian.math.finite_stochastic_processes._poisson_binomial_models import PoissonBinomialRequest
from jacobian.math.finite_stochastic_processes._poisson_binomial_operations import compute_poisson_binomial
from fractions import Fraction


def test_two_fair_coins() -> None:
    result = compute_poisson_binomial(PoissonBinomialRequest(probabilities=["1/2", "1/2"]))
    dist = [Fraction(d) for d in result.count_distribution]
    assert dist == [Fraction(1, 4), Fraction(1, 2), Fraction(1, 4)]


def test_single_certain() -> None:
    result = compute_poisson_binomial(PoissonBinomialRequest(probabilities=["1"]))
    dist = [Fraction(d) for d in result.count_distribution]
    assert dist == [Fraction(0), Fraction(1)]


def test_single_impossible() -> None:
    result = compute_poisson_binomial(PoissonBinomialRequest(probabilities=["0"]))
    dist = [Fraction(d) for d in result.count_distribution]
    assert dist == [Fraction(1), Fraction(0)]


def test_three_fair_coins() -> None:
    result = compute_poisson_binomial(PoissonBinomialRequest(probabilities=["1/2", "1/2", "1/2"]))
    dist = [Fraction(d) for d in result.count_distribution]
    assert dist == [Fraction(1, 8), Fraction(3, 8), Fraction(3, 8), Fraction(1, 8)]
    # Sum should be 1
    assert sum(dist) == Fraction(1)
