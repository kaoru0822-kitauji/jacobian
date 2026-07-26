"""Named Pydantic wire contracts for exact combinatorics capabilities."""

from __future__ import annotations

from typing import Self

from pydantic import Field, StrictInt, model_validator

from jacobian.contracts.exact import CanonicalInteger, CanonicalRational
from jacobian.contracts.results import ContractModel

_MAX_N = 1_000
_MAX_PARTS = 256


class NonnegativeIntegerRequest(ContractModel):
    n: StrictInt = Field(ge=0, le=_MAX_N)


class NonnegativePairRequest(ContractModel):
    n: StrictInt = Field(ge=0, le=_MAX_N)
    k: StrictInt = Field(ge=0, le=_MAX_N)


class IntegerListRequest(ContractModel):
    values: tuple[CanonicalInteger, ...] = Field(min_length=1, max_length=_MAX_PARTS)

    @model_validator(mode="after")
    def require_nonnegative_parts(self) -> Self:
        if any(int(v) < 0 for v in self.values):
            raise ValueError("integer list values must be nonnegative")
        return self


class IntegerResult(ContractModel):
    value: CanonicalInteger


class RationalResult(ContractModel):
    value: CanonicalRational
