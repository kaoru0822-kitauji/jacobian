"""Contracts for pinned Lean certificate workflows."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from jacobian.contracts.common import ArtifactUri
from jacobian.contracts.results import ContractModel, ResultEnvelope


class LeanEnvironment(StrEnum):
    CORE = "CORE"
    MATHLIB = "MATHLIB"


class LeanClaim(ContractModel):
    lean_contract_version: Literal["1"] = "1"
    environment: LeanEnvironment = LeanEnvironment.CORE
    statement: str = Field(min_length=1, max_length=2_000)
    allowed_axioms: tuple[str, ...] = ()


class LeanCandidate(ContractModel):
    lean_contract_version: Literal["1"] = "1"
    environment: LeanEnvironment = LeanEnvironment.CORE
    statement: str = Field(min_length=1, max_length=2_000)
    proof: str = Field(min_length=1, max_length=20_000)


class LeanVerifyResult(ContractModel):
    claim_uri: ArtifactUri
    candidate_uri: ArtifactUri
    certificate_uri: ArtifactUri
    result: ResultEnvelope
    cache_hit: bool = False
