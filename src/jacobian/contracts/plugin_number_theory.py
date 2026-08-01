"""Domain-owned request contracts for bounded number-theory plugins."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, StrictInt, model_validator

from jacobian.contracts.claims import ClaimSpec
from jacobian.contracts.plugin_protocol import PluginRequestContext
from jacobian.contracts.results import ContractModel


def _flatten_claim(value: object) -> object:
    if not isinstance(value, dict) or not isinstance(value.get("predicate"), dict):
        return value
    claim = ClaimSpec.model_validate(value)
    return {
        "predicate": claim.predicate.name,
        **claim.predicate.parameters,
        **claim.bounds,
    }


class ErdosStrausClaim(ContractModel):
    predicate: Literal["erdos_straus_range"]
    lower_bound: StrictInt = Field(ge=2, le=10_000)
    upper_bound: StrictInt = Field(ge=2, le=10_000)

    @model_validator(mode="before")
    @classmethod
    def flatten_generic_claim(cls, value: object) -> object:
        return _flatten_claim(value)

    @model_validator(mode="after")
    def require_ordered_range(self) -> Self:
        if self.upper_bound < self.lower_bound:
            raise ValueError("upper_bound must be at least lower_bound")
        return self


class ErdosStrausCandidate(ContractModel):
    lower_bound: StrictInt = Field(ge=2, le=10_000)
    upper_bound: StrictInt = Field(ge=2, le=10_000)

    @model_validator(mode="after")
    def require_ordered_range(self) -> Self:
        if self.upper_bound < self.lower_bound:
            raise ValueError("upper_bound must be at least lower_bound")
        return self


class ErdosStrausCapabilityRequest(PluginRequestContext):
    claim: ErdosStrausClaim
    candidate: ErdosStrausCandidate
    witness_role: Literal["DEFEATS_CANDIDATE", "SUPPORTS_CLAIM"] = "SUPPORTS_CLAIM"


__all__ = [
    "ErdosStrausCandidate",
    "ErdosStrausCapabilityRequest",
    "ErdosStrausClaim",
]
