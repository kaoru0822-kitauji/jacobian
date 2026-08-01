"""Domain-owned request contracts for bounded number-theory plugins."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, StrictInt, model_validator

from jacobian.contracts.claims import flatten_claim_spec
from jacobian.contracts.plugin_protocol import PluginRequestContext
from jacobian.contracts.results import ContractModel


class ErdosStrausClaim(ContractModel):
    predicate: Literal["erdos_straus_range"]
    lower_bound: StrictInt = Field(ge=2, le=10_000)
    upper_bound: StrictInt = Field(ge=2, le=10_000)

    @model_validator(mode="before")
    @classmethod
    def flatten_generic_claim(cls, value: object) -> object:
        return flatten_claim_spec(value)

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

    @model_validator(mode="after")
    def require_matching_range(self) -> Self:
        if (
            self.candidate.lower_bound != self.claim.lower_bound
            or self.candidate.upper_bound != self.claim.upper_bound
        ):
            raise ValueError("candidate range must exactly match the claim range")
        return self


__all__ = [
    "ErdosStrausCandidate",
    "ErdosStrausCapabilityRequest",
    "ErdosStrausClaim",
]
