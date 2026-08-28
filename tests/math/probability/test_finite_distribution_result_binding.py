"""Forgery regressions for externally parsed finite-distribution results."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian._exact import CanonicalRational
from jacobian.math.probability._distribution import (
    FiniteConditionRequest,
    FiniteConditionResult,
    FiniteConvolutionRequest,
    FiniteConvolutionResult,
    FiniteDistributionAtom,
    FinitePushforwardMapEntry,
    FinitePushforwardRequest,
    FinitePushforwardResult,
    FiniteRationalDistribution,
    FiniteRawMomentRequest,
    FiniteRawMomentResult,
)
from jacobian.math.probability._operations import (
    _condition,
    _convolution,
    _pushforward,
    _raw_moment,
)


def _q(numerator: int, denominator: int = 1) -> CanonicalRational:
    return CanonicalRational(num=str(numerator), den=str(denominator))


def _distribution() -> FiniteRationalDistribution:
    return FiniteRationalDistribution(
        atoms=(
            FiniteDistributionAtom(value=_q(0), probability=_q(1, 3)),
            FiniteDistributionAtom(value=_q(2), probability=_q(2, 3)),
        )
    )


def test_raw_moment_rejects_a_forged_contribution() -> None:
    result = _raw_moment(FiniteRawMomentRequest(atoms=_distribution().atoms, order=2))
    payload = result.model_dump(mode="json")
    payload["contributions"][1]["contribution"] = {"num": "1", "den": "3"}
    with pytest.raises(ValidationError):
        FiniteRawMomentResult.model_validate(payload)


def test_condition_rejects_a_distribution_not_bound_to_contributions() -> None:
    source = _distribution()
    result = _condition(
        FiniteConditionRequest(distribution=source, event_values=(_q(0), _q(2)))
    )
    payload = result.model_dump(mode="json")
    payload["contributions"][0]["conditioned_probability"] = {
        "num": "1",
        "den": "2",
    }
    with pytest.raises(ValidationError):
        FiniteConditionResult.model_validate(payload)


def test_pushforward_rejects_a_profile_not_bound_to_its_distribution() -> None:
    source = _distribution()
    result = _pushforward(
        FinitePushforwardRequest(
            distribution=source,
            mapping=(
                FinitePushforwardMapEntry(source=_q(0), target=_q(1)),
                FinitePushforwardMapEntry(source=_q(2), target=_q(1)),
            ),
        )
    )
    payload = result.model_dump(mode="json")
    payload["contributions"][0]["target"] = {"num": "2", "den": "1"}
    with pytest.raises(ValidationError):
        FinitePushforwardResult.model_validate(payload)


def test_convolution_rejects_a_forged_sum_value() -> None:
    source = _distribution()
    result = _convolution(FiniteConvolutionRequest(left=source, right=source))
    payload = result.model_dump(mode="json")
    payload["contributions"][0]["sum_value"] = {"num": "1", "den": "1"}
    with pytest.raises(ValidationError):
        FiniteConvolutionResult.model_validate(payload)
