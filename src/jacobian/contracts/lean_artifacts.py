"""Durable, environment-bound Lean proof-state and edit artifacts."""

from __future__ import annotations

from pydantic import Field, StrictInt, model_validator

from jacobian.contracts.common import ArtifactUri, Sha256Digest
from jacobian.contracts.lean_exploration import LeanLocalDeclaration, LeanTypedGoal
from jacobian.contracts.results import ContractModel, ExecutionStatus


class LeanEnvironmentIdentity(ContractModel):
    lean_toolchain_version: str = Field(min_length=1, max_length=128)
    project_source_digest: Sha256Digest
    provider_runtime_digest: Sha256Digest


class LeanProofState(ContractModel):
    """A replayable state is valid only under its exact environment identity."""

    source_artifact_uri: ArtifactUri
    declaration_or_command_position: StrictInt = Field(ge=0)
    typed_goals: tuple[LeanTypedGoal, ...] = Field(max_length=128)
    local_hypotheses: tuple[LeanLocalDeclaration, ...] = Field(max_length=256)
    metavariable_identifiers: tuple[str, ...] = Field(max_length=256)
    dependency_references: tuple[ArtifactUri, ...] = Field(max_length=256)
    environment_identity: LeanEnvironmentIdentity


class LeanProofEdit(ContractModel):
    """One requested edit and its bounded replay outcome."""

    before_state_uri: ArtifactUri
    requested_edit: str = Field(min_length=1, max_length=20_000)
    after_state_uri: ArtifactUri | None = None
    diagnostics: tuple[str, ...] = Field(max_length=64)
    execution_status: ExecutionStatus
    environment_identity: LeanEnvironmentIdentity

    @model_validator(mode="after")
    def bind_after_state_to_success(self) -> LeanProofEdit:
        if self.execution_status is ExecutionStatus.COMPLETED:
            if self.after_state_uri is None:
                raise ValueError("completed Lean proof edits require an after-state")
        elif self.after_state_uri is not None:
            raise ValueError("only completed Lean proof edits may have an after-state")
        return self


__all__ = [
    "LeanEnvironmentIdentity",
    "LeanProofEdit",
    "LeanProofState",
]
