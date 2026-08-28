"""Contracts for exact finite rational-distribution operations."""

from __future__ import annotations

from fractions import Fraction
from itertools import pairwise
from typing import Literal, Self

from pydantic import Field, StrictInt, model_validator

from jacobian._exact import CanonicalRational, require_bounded_rational
from jacobian._models import StrictModel
from jacobian.math.probability._models import (
    MAX_INPUT_RATIONAL_DIGITS,
    MAX_RESULT_RATIONAL_DIGITS,
    _require_strictly_increasing,
    _validation_error,
)

MAX_FINITE_DISTRIBUTION_ATOMS = 256
MAX_FINITE_CONVOLUTION_PAIRS = 4096


class FiniteDistributionAtom(StrictModel):
    value: CanonicalRational
    probability: CanonicalRational

    @model_validator(mode="after")
    def require_bounded_nonnegative_probability(self) -> Self:
        require_bounded_rational(
            self.value,
            max_digits=MAX_RESULT_RATIONAL_DIGITS,
            label="finite-distribution atom",
        )
        require_bounded_rational(
            self.probability,
            max_digits=MAX_RESULT_RATIONAL_DIGITS,
            label="finite-distribution probability",
        )
        if self.probability.as_fraction() < 0:
            raise _validation_error(
                "finite-distribution probabilities must be nonnegative"
            )
        return self


class FiniteRationalDistribution(StrictModel):
    atoms: tuple[FiniteDistributionAtom, ...] = Field(
        min_length=1,
        max_length=MAX_FINITE_DISTRIBUTION_ATOMS,
    )

    @model_validator(mode="after")
    def require_canonical_probability_distribution(self) -> Self:
        _require_strictly_increasing(
            tuple(atom.value for atom in self.atoms),
            label="finite-distribution support values",
        )
        if (
            sum(
                (atom.probability.as_fraction() for atom in self.atoms),
                start=Fraction(),
            )
            != 1
        ):
            raise _validation_error(
                "finite-distribution probabilities must sum exactly to 1"
            )
        return self


def require_input_distribution(
    atoms: tuple[FiniteDistributionAtom, ...],
    *,
    require_canonical: bool,
) -> tuple[Fraction, ...]:
    values = tuple(atom.value.as_fraction() for atom in atoms)
    if len(values) != len(set(values)):
        raise _validation_error("finite-distribution support values must be unique")
    if require_canonical and any(left >= right for left, right in pairwise(values)):
        raise _validation_error(
            "finite-distribution support values must be strictly increasing"
        )
    for atom in atoms:
        require_bounded_rational(
            atom.value,
            max_digits=MAX_INPUT_RATIONAL_DIGITS,
            label="finite-distribution input atom",
        )
        require_bounded_rational(
            atom.probability,
            max_digits=MAX_INPUT_RATIONAL_DIGITS,
            label="finite-distribution input probability",
        )
    if (
        sum(
            (atom.probability.as_fraction() for atom in atoms),
            start=Fraction(),
        )
        != 1
    ):
        raise _validation_error(
            "finite-distribution probabilities must sum exactly to 1"
        )
    return values


class FiniteRawMomentRequest(StrictModel):
    atoms: tuple[FiniteDistributionAtom, ...] = Field(
        min_length=1,
        max_length=MAX_FINITE_DISTRIBUTION_ATOMS,
    )
    order: StrictInt = Field(ge=0, le=128)


class FiniteRawMomentContribution(StrictModel):
    value: CanonicalRational
    probability: CanonicalRational
    powered_value: CanonicalRational
    contribution: CanonicalRational


class FiniteRawMomentResult(StrictModel):
    order: StrictInt = Field(ge=0, le=128)
    moment: CanonicalRational
    contributions: tuple[FiniteRawMomentContribution, ...] = Field(
        min_length=1,
        max_length=MAX_FINITE_DISTRIBUTION_ATOMS,
    )

    @classmethod
    def _from_kernel(
        cls,
        *,
        order: int,
        moment: CanonicalRational,
        contributions: tuple[FiniteRawMomentContribution, ...],
    ) -> Self:
        return cls.model_construct(
            order=order, moment=moment, contributions=contributions
        )


class FiniteEventRequest(StrictModel):
    distribution: FiniteRationalDistribution
    event_values: tuple[CanonicalRational, ...] = Field(
        max_length=MAX_FINITE_DISTRIBUTION_ATOMS
    )


class FiniteConditionRequest(FiniteEventRequest):
    """A finite event known to have positive exact probability."""


class FiniteEventProbabilityResult(StrictModel):
    event_probability: CanonicalRational
    selected_atoms: tuple[FiniteDistributionAtom, ...] = Field(
        max_length=MAX_FINITE_DISTRIBUTION_ATOMS
    )

    @classmethod
    def _from_kernel(
        cls,
        *,
        event_probability: CanonicalRational,
        selected_atoms: tuple[FiniteDistributionAtom, ...],
    ) -> Self:
        return cls.model_construct(
            event_probability=event_probability,
            selected_atoms=selected_atoms,
        )


class FiniteConditionalContribution(StrictModel):
    value: CanonicalRational
    source_probability: CanonicalRational
    conditioned_probability: CanonicalRational

    @model_validator(mode="after")
    def require_bounded_nonnegative_masses(self) -> Self:
        for label, value in (
            ("conditional value", self.value),
            ("conditional source probability", self.source_probability),
            ("conditioned probability", self.conditioned_probability),
        ):
            require_bounded_rational(
                value,
                max_digits=MAX_RESULT_RATIONAL_DIGITS,
                label=label,
            )
        if (
            self.source_probability.as_fraction() < 0
            or self.conditioned_probability.as_fraction() < 0
        ):
            raise _validation_error(
                "conditional contribution masses must be nonnegative"
            )
        return self


class FiniteConditionResult(StrictModel):
    event_probability: CanonicalRational
    distribution: FiniteRationalDistribution
    contributions: tuple[FiniteConditionalContribution, ...] = Field(
        min_length=1,
        max_length=MAX_FINITE_DISTRIBUTION_ATOMS,
    )

    @classmethod
    def _from_kernel(
        cls,
        *,
        event_probability: CanonicalRational,
        distribution: FiniteRationalDistribution,
        contributions: tuple[FiniteConditionalContribution, ...],
    ) -> Self:
        return cls.model_construct(
            event_probability=event_probability,
            distribution=distribution,
            contributions=contributions,
        )


class FinitePushforwardMapEntry(StrictModel):
    source: CanonicalRational
    target: CanonicalRational


class FinitePushforwardRequest(StrictModel):
    distribution: FiniteRationalDistribution
    mapping: tuple[FinitePushforwardMapEntry, ...] = Field(
        min_length=1,
        max_length=MAX_FINITE_DISTRIBUTION_ATOMS,
    )


class FinitePushforwardContribution(StrictModel):
    source: CanonicalRational
    target: CanonicalRational
    probability: CanonicalRational

    @model_validator(mode="after")
    def require_bounded_nonnegative_mass(self) -> Self:
        for label, value in (
            ("pushforward source", self.source),
            ("pushforward target", self.target),
            ("pushforward probability", self.probability),
        ):
            require_bounded_rational(
                value,
                max_digits=MAX_RESULT_RATIONAL_DIGITS,
                label=label,
            )
        if self.probability.as_fraction() < 0:
            raise _validation_error("pushforward contribution mass must be nonnegative")
        return self


class FinitePushforwardResult(StrictModel):
    distribution: FiniteRationalDistribution
    contributions: tuple[FinitePushforwardContribution, ...] = Field(
        min_length=1,
        max_length=MAX_FINITE_DISTRIBUTION_ATOMS,
    )

    @classmethod
    def _from_kernel(
        cls,
        *,
        distribution: FiniteRationalDistribution,
        contributions: tuple[FinitePushforwardContribution, ...],
    ) -> Self:
        return cls.model_construct(
            distribution=distribution,
            contributions=contributions,
        )


class FiniteConvolutionRequest(StrictModel):
    left: FiniteRationalDistribution
    right: FiniteRationalDistribution


class FiniteConvolutionContribution(StrictModel):
    left_value: CanonicalRational
    right_value: CanonicalRational
    sum_value: CanonicalRational
    probability: CanonicalRational

    @model_validator(mode="after")
    def require_bounded_nonnegative_mass(self) -> Self:
        for label, value in (
            ("convolution left value", self.left_value),
            ("convolution right value", self.right_value),
            ("convolution sum value", self.sum_value),
            ("convolution probability", self.probability),
        ):
            require_bounded_rational(
                value,
                max_digits=MAX_RESULT_RATIONAL_DIGITS,
                label=label,
            )
        if self.probability.as_fraction() < 0:
            raise _validation_error("convolution contribution mass must be nonnegative")
        return self


class FiniteConvolutionResult(StrictModel):
    distribution: FiniteRationalDistribution
    contributions: tuple[FiniteConvolutionContribution, ...] = Field(
        min_length=1,
        max_length=MAX_FINITE_CONVOLUTION_PAIRS,
    )
    independence: Literal["PRODUCT_MEASURE"] = "PRODUCT_MEASURE"

    @classmethod
    def _from_kernel(
        cls,
        *,
        distribution: FiniteRationalDistribution,
        contributions: tuple[FiniteConvolutionContribution, ...],
    ) -> Self:
        return cls.model_construct(
            distribution=distribution,
            contributions=contributions,
            independence="PRODUCT_MEASURE",
        )


__all__ = [
    "MAX_FINITE_CONVOLUTION_PAIRS",
    "MAX_FINITE_DISTRIBUTION_ATOMS",
    "FiniteConditionRequest",
    "FiniteConditionResult",
    "FiniteConditionalContribution",
    "FiniteConvolutionContribution",
    "FiniteConvolutionRequest",
    "FiniteConvolutionResult",
    "FiniteDistributionAtom",
    "FiniteEventProbabilityResult",
    "FiniteEventRequest",
    "FinitePushforwardContribution",
    "FinitePushforwardMapEntry",
    "FinitePushforwardRequest",
    "FinitePushforwardResult",
    "FiniteRationalDistribution",
    "FiniteRawMomentContribution",
    "FiniteRawMomentRequest",
    "FiniteRawMomentResult",
    "require_input_distribution",
]
