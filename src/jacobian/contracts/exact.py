"""Canonical exact scalar wire values."""

from __future__ import annotations

from fractions import Fraction
from typing import Annotated, Self

from pydantic import StringConstraints, model_validator

from jacobian.contracts.results import ContractModel

CanonicalInteger = Annotated[
    str,
    StringConstraints(
        pattern=r"^-?(?:0|[1-9][0-9]*)$",
        strict=True,
    ),
]


class CanonicalRational(ContractModel):
    num: CanonicalInteger
    den: CanonicalInteger

    @model_validator(mode="after")
    def require_reduced_positive_denominator(self) -> Self:
        denominator = int(self.den)
        if denominator == 0:
            raise ValueError("rational denominator cannot be zero")
        value = Fraction(int(self.num), denominator)
        if self.num != str(value.numerator) or self.den != str(value.denominator):
            raise ValueError(
                "rational must be reduced with a positive denominator and canonical zero"
            )
        return self

    def as_fraction(self) -> Fraction:
        return Fraction(int(self.num), int(self.den))
