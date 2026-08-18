"""Typed wire contracts for Markov chain operations."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from jacobian._exact import CanonicalRational
from jacobian._models import StrictModel


class TransitionMatrixRequest(StrictModel):
    """A finite stochastic transition matrix with rational entries."""

    matrix: tuple[tuple[CanonicalRational, ...], ...] = Field(
        min_length=1, max_length=32
    )

    @model_validator(mode="after")
    def require_stochastic_square_matrix(self) -> Self:
        dimension = len(self.matrix)
        if any(len(row) != dimension for row in self.matrix):
            raise ValueError("transition matrix must be square")
        for row in self.matrix:
            values = tuple(value.as_fraction() for value in row)
            if any(value < 0 for value in values):
                raise ValueError("transition probabilities must be nonnegative")
            if sum(values) != 1:
                raise ValueError("each transition row must sum to one")
        return self


class ExtremeStationaryDistribution(StrictModel):
    """One canonical extreme point supported on a closed class."""

    closed_class: tuple[int, ...] = Field(min_length=1)
    distribution: tuple[CanonicalRational, ...] = Field(min_length=1)


class StationaryDistributionResult(StrictModel):
    """Extreme points of the finite chain's stationary-distribution simplex."""

    extreme_distributions: tuple[ExtremeStationaryDistribution, ...] = Field(
        min_length=1
    )
    unique: bool
    method: Literal["CLOSED_CLASS_EXACT_LINEAR_SYSTEM"] = (
        "CLOSED_CLASS_EXACT_LINEAR_SYSTEM"
    )

    @model_validator(mode="after")
    def bind_stationary_family(self) -> Self:
        dimensions = {len(item.distribution) for item in self.extreme_distributions}
        if len(dimensions) != 1:
            raise ValueError("stationary distributions must share one dimension")
        classes = tuple(item.closed_class for item in self.extreme_distributions)
        if classes != tuple(sorted(classes)) or len(classes) != len(set(classes)):
            raise ValueError("closed classes must be unique and sorted")
        if self.unique != (len(self.extreme_distributions) == 1):
            raise ValueError("unique must match the number of extreme distributions")
        for item in self.extreme_distributions:
            values = tuple(value.as_fraction() for value in item.distribution)
            if any(value < 0 for value in values) or sum(values) != 1:
                raise ValueError(
                    "each stationary distribution must be nonnegative and normalized"
                )
            support = tuple(index for index, value in enumerate(values) if value > 0)
            if support != item.closed_class:
                raise ValueError(
                    "each extreme distribution must be supported on its closed class"
                )
        return self


class ErgodicDecisionResult(StrictModel):
    is_ergodic: bool
    is_irreducible: bool
    is_aperiodic: bool
