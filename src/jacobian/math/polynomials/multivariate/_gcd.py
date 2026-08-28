"""Contracts for multivariate polynomial GCD over ``QQ``."""

from __future__ import annotations

from typing import Literal

from jacobian._models import StrictModel
from jacobian.math.polynomials.values import RationalPolynomial


class MultivariateGcdRequest(StrictModel):
    """Two multivariate polynomials in ``QQ[x_1, ..., x_n]``."""

    left: RationalPolynomial
    right: RationalPolynomial


class MultivariateGcdResult(StrictModel):
    gcd: RationalPolynomial
    convention: Literal["MONIC_ASSOCIATE"] = "MONIC_ASSOCIATE"


__all__ = ["MultivariateGcdRequest", "MultivariateGcdResult"]
