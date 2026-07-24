"""Model-facing contracts for extensible mathematical capabilities."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from jacobian.canonical import canonicalize_json
from jacobian.contracts.common import ArtifactUri
from jacobian.contracts.results import ContractModel, Execution

CapabilityId = Annotated[
    str,
    StringConstraints(
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$",
        min_length=3,
        max_length=128,
        strict=True,
    ),
]


class CapabilityMode(StrEnum):
    """The low-friction exploration and explicit verification lanes."""

    EXPLORE = "EXPLORE"
    VERIFY = "VERIFY"


class CapabilityAssuranceLevel(StrEnum):
    """Coarse model-facing assurance without hiding the detailed result record."""

    HEURISTIC = "HEURISTIC"
    COMPUTED = "COMPUTED"
    VERIFIED = "VERIFIED"


class CapabilityDescriptor(ContractModel):
    """One stable operation advertised by an operator-installed adapter."""

    descriptor_version: Literal["1"] = "1"
    capability_id: CapabilityId
    version: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=512)
    provider: str = Field(min_length=1, max_length=128)
    modes: tuple[CapabilityMode, ...]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    read_only: bool = False
    records_episode: bool = True
    tags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_modes_and_canonical_schemas(self) -> Self:
        if not self.modes:
            raise ValueError("a capability must support at least one mode")
        if len(set(self.modes)) != len(self.modes):
            raise ValueError("capability modes must be unique")
        canonicalize_json(self.input_schema)
        canonicalize_json(self.output_schema)
        return self


class CapabilityRequest(ContractModel):
    request_version: Literal["1"] = "1"
    capability_id: CapabilityId
    mode: CapabilityMode = CapabilityMode.EXPLORE
    input: dict[str, Any]

    @model_validator(mode="after")
    def require_canonical_input(self) -> Self:
        canonicalize_json(self.input)
        return self


class CapabilityAssurance(ContractModel):
    level: CapabilityAssuranceLevel
    basis: str = Field(min_length=1, max_length=1024)
    verification_record_uri: ArtifactUri | None = None

    @model_validator(mode="after")
    def bind_verified_assurance(self) -> Self:
        if (
            self.level is CapabilityAssuranceLevel.VERIFIED
            and self.verification_record_uri is None
        ):
            raise ValueError("verified capability assurance requires a record URI")
        if (
            self.level is not CapabilityAssuranceLevel.VERIFIED
            and self.verification_record_uri is not None
        ):
            raise ValueError(
                "only verified capability assurance may carry a record URI"
            )
        return self


class CapabilityDiagnostic(ContractModel):
    """Actionable, stage-aware failure information without a truth claim."""

    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    stage: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    message: str = Field(min_length=1, max_length=1024)
    path: str | None = Field(default=None, max_length=512)
    schema_uri: ArtifactUri | None = None
    expected: str | None = Field(default=None, max_length=1024)
    actual_type: str | None = Field(default=None, max_length=128)
    hint: str | None = Field(default=None, max_length=1024)


class CapabilityResult(ContractModel):
    """Compact result shared by local, MCP, and remote capability adapters."""

    response_version: Literal["1"] = "1"
    capability_id: CapabilityId
    capability_version: str = Field(min_length=1, max_length=64)
    mode: CapabilityMode
    execution: Execution
    output: dict[str, Any] = Field(default_factory=dict)
    scope: dict[str, Any] = Field(default_factory=dict)
    diagnostics: tuple[CapabilityDiagnostic, ...] = ()
    assurance: CapabilityAssurance
    artifact_uris: tuple[ArtifactUri, ...] = ()
    episode_uri: ArtifactUri | None = None

    @model_validator(mode="after")
    def enforce_lane_and_canonical_output(self) -> Self:
        canonicalize_json(self.output)
        canonicalize_json(self.scope)
        if self.execution.status.value == "COMPLETED" and self.diagnostics:
            raise ValueError("completed capability execution cannot carry diagnostics")
        if (
            self.assurance.level is CapabilityAssuranceLevel.VERIFIED
            and self.mode is not CapabilityMode.VERIFY
        ):
            raise ValueError("the exploration lane cannot return verified assurance")
        if (
            self.execution.status.value != "COMPLETED"
            and self.assurance.level is CapabilityAssuranceLevel.VERIFIED
        ):
            raise ValueError("failed capability execution cannot be verified")
        return self


class CapabilityCatalog(ContractModel):
    catalog_version: Literal["1"] = "1"
    capabilities: tuple[CapabilityDescriptor, ...]
