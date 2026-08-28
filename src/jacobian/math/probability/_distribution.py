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

    @model_validator(mode="after")
    def bind_moment_contributions(self) -> Self:
        total = Fraction()
        source_values: set[Fraction] = set()
        source_mass = Fraction()
        for item in self.contributions:
            value = item.value.as_fraction()
            probability = item.probability.as_fraction()
            if probability < 0:
                raise _validation_error(
                    "finite raw-moment source probabilities must be nonnegative"
                )
            if value in source_values:
                raise _validation_error(
                    "finite raw-moment contributions must have unique source values"
                )
            source_values.add(value)
            source_mass += probability
            powered = value**self.order
            if item.powered_value.as_fraction() != powered:
                raise _validation_error(
                    "finite raw-moment powered values must match the retained order"
                )
            contribution = probability * powered
            if item.contribution.as_fraction() != contribution:
                raise _validation_error(
                    "finite raw-moment contributions must match value and probability"
                )
            total += contribution
        if source_mass != 1:
            raise _validation_error(
                "finite raw-moment source probabilities must sum exactly to 1"
            )
        if self.moment.as_fraction() != total:
            raise _validation_error(
                "finite raw moment must equal the sum of retained contributions"
            )
        return self

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

    @model_validator(mode="after")
    def bind_selected_probability(self) -> Self:
        selected_values = tuple(
            atom.value.as_fraction() for atom in self.selected_atoms
        )
        if selected_values != tuple(sorted(set(selected_values))):
            raise _validation_error(
                "finite event selected atoms must be unique and canonically ordered"
            )
        expected = sum(
            (atom.probability.as_fraction() for atom in self.selected_atoms),
            start=Fraction(),
        )
        if self.event_probability.as_fraction() != expected:
            raise _validation_error(
                "finite event probability must equal the selected-atom mass"
            )
        return self

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

    @model_validator(mode="after")
    def bind_conditional_profile(self) -> Self:
        event_probability = self.event_probability.as_fraction()
        if event_probability <= 0:
            raise _validation_error("finite conditioning requires positive event mass")
        expected_atoms: list[tuple[Fraction, Fraction]] = []
        for item in self.contributions:
            source_probability = item.source_probability.as_fraction()
            conditioned = source_probability / event_probability
            if item.conditioned_probability.as_fraction() != conditioned:
                raise _validation_error(
                    "conditioned probabilities must equal source mass divided by event mass"
                )
            expected_atoms.append((item.value.as_fraction(), conditioned))
        if (
            sum(
                (item.source_probability.as_fraction() for item in self.contributions),
                start=Fraction(),
            )
            != event_probability
        ):
            raise _validation_error(
                "conditioning event mass must equal the retained source contributions"
            )
        actual_atoms = [
            (atom.value.as_fraction(), atom.probability.as_fraction())
            for atom in self.distribution.atoms
        ]
        if actual_atoms != sorted(expected_atoms):
            raise _validation_error(
                "conditioned distribution must aggregate the retained contributions"
            )
        return self

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

    @model_validator(mode="after")
    def bind_pushforward_profile(self) -> Self:
        expected: dict[Fraction, Fraction] = {}
        source_values: set[Fraction] = set()
        source_mass = Fraction()
        for item in self.contributions:
            source = item.source.as_fraction()
            if source in source_values:
                raise _validation_error(
                    "pushforward contributions must have unique source values"
                )
            source_values.add(source)
            source_mass += item.probability.as_fraction()
            target = item.target.as_fraction()
            expected[target] = (
                expected.get(target, Fraction()) + item.probability.as_fraction()
            )
        if source_mass != 1:
            raise _validation_error(
                "pushforward source probabilities must sum exactly to 1"
            )
        actual = {
            atom.value.as_fraction(): atom.probability.as_fraction()
            for atom in self.distribution.atoms
        }
        if actual != expected:
            raise _validation_error(
                "pushforward distribution must aggregate the retained contributions"
            )
        return self

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

    @model_validator(mode="after")
    def bind_convolution_profile(self) -> Self:
        expected: dict[Fraction, Fraction] = {}
        joint: dict[tuple[Fraction, Fraction], Fraction] = {}
        left_marginal: dict[Fraction, Fraction] = {}
        right_marginal: dict[Fraction, Fraction] = {}
        for item in self.contributions:
            left = item.left_value.as_fraction()
            right = item.right_value.as_fraction()
            if item.sum_value.as_fraction() != left + right:
                raise _validation_error(
                    "convolution sum values must equal their retained summands"
                )
            target = left + right
            pair = (left, right)
            if pair in joint:
                raise _validation_error(
                    "convolution contributions must contain each source pair once"
                )
            probability = item.probability.as_fraction()
            joint[pair] = probability
            left_marginal[left] = left_marginal.get(left, Fraction()) + probability
            right_marginal[right] = right_marginal.get(right, Fraction()) + probability
            expected[target] = expected.get(target, Fraction()) + probability
        expected_pairs = {
            (left, right) for left in left_marginal for right in right_marginal
        }
        if set(joint) != expected_pairs or any(
            probability != left_marginal[left] * right_marginal[right]
            for (left, right), probability in joint.items()
        ):
            raise _validation_error(
                "convolution contributions must encode one complete product measure"
            )
        actual = {
            atom.value.as_fraction(): atom.probability.as_fraction()
            for atom in self.distribution.atoms
        }
        if actual != expected:
            raise _validation_error(
                "convolution distribution must aggregate the retained contributions"
            )
        return self

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
