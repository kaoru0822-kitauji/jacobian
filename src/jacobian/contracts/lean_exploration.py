"""Contracts for replayable exploratory Lean operations."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, StrictInt, model_validator

from jacobian.contracts.common import ArtifactUri
from jacobian.contracts.lean import LeanEnvironment
from jacobian.contracts.results import ContractModel


class LeanProofStateRequest(ContractModel):
    environment: LeanEnvironment = LeanEnvironment.CORE
    statement: str = Field(min_length=1, max_length=2_000)
    proof_prefix: tuple[str, ...] = Field(default=(), max_length=32)
    tactic: str = Field(min_length=1, max_length=1_000)
    max_goals: StrictInt = Field(default=32, ge=1, le=64)
    max_local_declarations: StrictInt = Field(default=128, ge=1, le=256)
    max_rendered_bytes: StrictInt = Field(default=65_536, ge=1_024, le=262_144)

    @model_validator(mode="after")
    def require_bounded_prefix(self) -> Self:
        if any(
            not tactic.strip() or len(tactic) > 1_000 for tactic in self.proof_prefix
        ):
            raise ValueError("proof-prefix tactics must be nonempty and bounded")
        return self


class LeanLocalDeclaration(ContractModel):
    user_name: str = Field(min_length=1, max_length=512)
    binder_info: str = Field(min_length=1, max_length=64)
    type: str = Field(min_length=1, max_length=20_000)
    value: str | None = Field(default=None, min_length=1, max_length=20_000)


class LeanTypedGoal(ContractModel):
    goal_index: StrictInt = Field(ge=0, le=63)
    target_type: str = Field(min_length=1, max_length=20_000)
    local_declarations: tuple[LeanLocalDeclaration, ...] = Field(max_length=256)


class LeanProofStateTransitionArtifact(ContractModel):
    transition_schema_version: Literal["2"] = "2"
    environment: LeanEnvironment
    statement: str
    proof_prefix: tuple[str, ...]
    tactic: str
    replay_source: str
    goals: tuple[str, ...]
    typed_goals: tuple[LeanTypedGoal, ...]
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
        if self.goal_count != len(self.typed_goals):
            raise ValueError("goal count differs from returned typed goals")
        if tuple(goal.goal_index for goal in self.typed_goals) != tuple(
            range(self.goal_count)
        ):
            raise ValueError("typed goal indices must be contiguous")
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
    backend_module: Literal["Mathlib.Tactic"] = "Mathlib.Tactic"
    tactic_replayed: bool
    declaration_name_extraction: Literal["DISPLAY_TEXT_HEURISTIC"] = (
        "DISPLAY_TEXT_HEURISTIC"
    )


class LeanPremiseRetrievalArtifact(ContractModel):
    retrieval_schema_version: Literal["2"] = "2"
    environment: Literal["MATHLIB"] = "MATHLIB"
    statement: str
    proof_prefix: tuple[str, ...]
    candidates: tuple[LeanPremiseCandidate, ...]
    exhaustive: Literal[False] = False
    retrieval_api: Literal["MATHLIB_EXACT_TACTIC"] = "MATHLIB_EXACT_TACTIC"
    api_stability: Literal["EXPERIMENTAL_TACTIC_DIAGNOSTIC"] = (
        "EXPERIMENTAL_TACTIC_DIAGNOSTIC"
    )
    goal_context_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    lean_version: str
    lean_commit: str
    mathlib_commit: str


class LeanPremiseRetrievalOutput(LeanPremiseRetrievalArtifact):
    retrieval_uri: ArtifactUri
    verification: Literal["UNVERIFIED"] = "UNVERIFIED"
