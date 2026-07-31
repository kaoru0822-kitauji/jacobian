"""Trust-labeled research-memory contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import Field, RootModel, StrictInt, StrictStr, model_validator

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityId,
    CapabilityMode,
)
from jacobian.contracts.common import ArtifactUri, Sha256Digest
from jacobian.contracts.results import ContractModel

MemoryFilterValue = Annotated[str, Field(min_length=1, max_length=128)]


class PersistedTags(RootModel[tuple[StrictStr, ...]]):
    """Canonical JSON array stored in the research-memory index."""


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


class KnowledgeSearchRequest(ContractModel):
    query: str = Field(default="", max_length=512)
    capability_id: CapabilityId | None = None
    domains: tuple[MemoryFilterValue, ...] = Field(
        default=(),
        max_length=32,
        json_schema_extra={"uniqueItems": True},
    )
    tags_all: tuple[MemoryFilterValue, ...] = Field(
        default=(),
        max_length=32,
        json_schema_extra={"uniqueItems": True},
    )
    tags_any: tuple[MemoryFilterValue, ...] = Field(
        default=(),
        max_length=32,
        json_schema_extra={"uniqueItems": True},
    )
    failure_stages: tuple[MemoryFilterValue, ...] = Field(
        default=(),
        max_length=32,
        json_schema_extra={"uniqueItems": True},
    )
    failure_classifications: tuple[MemoryFilterValue, ...] = Field(
        default=(),
        max_length=32,
        json_schema_extra={"uniqueItems": True},
    )
    assurance_level: CapabilityAssuranceLevel | None = None
    cutoff: datetime | None = None
    limit: StrictInt = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def require_unique_filters(self) -> Self:
        for field_name in (
            "domains",
            "tags_all",
            "tags_any",
            "failure_stages",
            "failure_classifications",
        ):
            values = getattr(self, field_name)
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must contain unique values")
        return self


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
