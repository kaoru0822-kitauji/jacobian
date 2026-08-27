"""Typed contracts for exact Poisson-binomial count distributions."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, StringConstraints

from jacobian._models import StrictModel
from jacobian.canonical import format_canonical_integer, parse_canonical_integer

MAX_PROBABILITIES: int = 500

RationalString = Annotated[
    str,
    StringConstraints(
        pattern=r"^(?:0|-?[1-9][0-9]*)(?:\/[1-9][0-9]*)?$",
        max_length=100,
        strict=True,
    ),
]


class PoissonBinomialRequest(StrictModel):
    """A list of rational Bernoulli success probabilities."""

    probabilities: list[RationalString] = Field(max_length=MAX_PROBABILITIES)


class PoissonBinomialResult(StrictModel):
    """Exact Poisson-binomial count distribution as rational strings."""

    probabilities: list[str]
    count_distribution: list[str]


__all__ = [
    "PoissonBinomialRequest",
    "PoissonBinomialResult",
    "MAX_PROBABILITIES",
]
