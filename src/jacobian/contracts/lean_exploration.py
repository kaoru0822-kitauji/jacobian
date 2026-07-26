"""Contracts for replayable exploratory Lean operations."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from jacobian.contracts.common import ArtifactUri
from jacobian.contracts.lean import LeanEnvironment
from jacobian.contracts.results import ContractModel


class LeanProofStateRequest(ContractModel):
    environment: LeanEnvironment = LeanEnvironment.CORE
    statement: str = Field(min_length=1, max_length=2_000)
    proof_prefix: tuple[str, ...] = Field(default=(), max_length=32)
    tactic: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def require_bounded_prefix(self) -> Self:
        if any(
            not tactic.strip() or len(tactic) > 1_000 for tactic in self.proof_prefix
        ):
            raise ValueError("proof-prefix tactics must be nonempty and bounded")
        return self


class LeanProofStateTransitionArtifact(ContractModel):
    transition_schema_version: Literal["1"] = "1"
    environment: LeanEnvironment
    statement: str
    proof_prefix: tuple[str, ...]
    tactic: str
    replay_source: str
    goals: tuple[str, ...]
    goal_count: int = Field(ge=0)
    completed: bool
    messages: tuple[str, ...]
    lean_version: str
    lean_commit: str
    mathlib_commit: str | None = None

    @model_validator(mode="after")
    def require_consistent_goal_summary(self) -> Self:
        if self.goal_count != len(self.goals):
            raise ValueError("goal count differs from returned goals")
        if self.completed != (self.goal_count == 0):
            raise ValueError("completion differs from returned goals")
        return self


class LeanProofStateOutput(LeanProofStateTransitionArtifact):
    transition_uri: ArtifactUri
    verification: Literal["UNVERIFIED"] = "UNVERIFIED"


class LeanPremiseRetrievalRequest(ContractModel):
    environment: Literal["MATHLIB"] = "MATHLIB"
    statement: str = Field(min_length=1, max_length=2_000)
    proof_prefix: tuple[str, ...] = Field(default=(), max_length=32)
    limit: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def require_bounded_prefix(self) -> Self:
        if any(
            not tactic.strip() or len(tactic) > 1_000 for tactic in self.proof_prefix
        ):
            raise ValueError("proof-prefix tactics must be nonempty and bounded")
        return self


class LeanPremiseCandidate(ContractModel):
    rank: int = Field(ge=1, le=20)
    tactic: str = Field(min_length=1, max_length=2_000)
    declaration_names: tuple[str, ...] = ()
    backend: Literal["mathlib.exact?"] = "mathlib.exact?"


class LeanPremiseRetrievalArtifact(ContractModel):
    retrieval_schema_version: Literal["1"] = "1"
    environment: Literal["MATHLIB"] = "MATHLIB"
    statement: str
    proof_prefix: tuple[str, ...]
    candidates: tuple[LeanPremiseCandidate, ...]
    exhaustive: Literal[False] = False
    lean_version: str
    lean_commit: str
    mathlib_commit: str


class LeanPremiseRetrievalOutput(LeanPremiseRetrievalArtifact):
    retrieval_uri: ArtifactUri
    verification: Literal["UNVERIFIED"] = "UNVERIFIED"
