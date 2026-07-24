"""Trust-labeled research-memory contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, StrictInt

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityId,
    CapabilityMode,
)
from jacobian.contracts.common import ArtifactUri
from jacobian.contracts.results import ContractModel


class ResearchEpisode(ContractModel):
    episode_version: Literal["1"] = "1"
    capability_id: CapabilityId
    capability_version: str = Field(min_length=1, max_length=64)
    mode: CapabilityMode
    request: dict[str, Any]
    result: dict[str, Any]
    assurance_level: CapabilityAssuranceLevel
    verification_record_uri: ArtifactUri | None = None
    artifact_uris: tuple[ArtifactUri, ...] = ()
    summary: str = Field(default="", max_length=1024)
    tags: tuple[str, ...] = ()


class MemoryHit(ContractModel):
    episode_uri: ArtifactUri
    capability_id: CapabilityId
    mode: CapabilityMode
    assurance_level: CapabilityAssuranceLevel
    summary: str
    tags: tuple[str, ...] = ()
    created_at: datetime
    score: StrictInt = Field(ge=0, le=1000)


class MemorySearchResult(ContractModel):
    query: str
    hits: tuple[MemoryHit, ...]
    cutoff: datetime | None = None
