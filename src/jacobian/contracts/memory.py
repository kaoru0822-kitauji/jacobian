"""Trust-labeled research-memory contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import Field, StrictInt, model_validator

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityId,
    CapabilityMode,
)
from jacobian.contracts.common import ArtifactUri, Sha256Digest
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
    matched_query_terms: tuple[str, ...] = ()
    matched_filters: tuple[str, ...] = ()


class MemorySearchResult(ContractModel):
    query: str
    hits: tuple[MemoryHit, ...]
    cutoff: datetime | None = None
    index_snapshot: Sha256Digest
    indexed_episode_count: StrictInt = Field(ge=0)
    total_matches: StrictInt = Field(ge=0)
    returned_count: StrictInt = Field(ge=0)
    truncated: bool
    completeness: Literal["COMPLETE", "PARTIAL"]

    @model_validator(mode="after")
    def bind_counts_and_completeness(self) -> Self:
        if self.returned_count != len(self.hits):
            raise ValueError("returned_count must equal the number of hits")
        if self.returned_count > self.total_matches:
            raise ValueError("returned_count cannot exceed total_matches")
        expected_truncated = self.returned_count < self.total_matches
        if self.truncated != expected_truncated:
            raise ValueError("truncated must reflect omitted matching hits")
        expected_completeness = "PARTIAL" if self.truncated else "COMPLETE"
        if self.completeness != expected_completeness:
            raise ValueError("completeness must reflect result truncation")
        return self
