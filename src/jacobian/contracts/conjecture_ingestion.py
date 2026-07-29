"""Contracts for license-aware external conjecture ingestion."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from jacobian.contracts.common import ArtifactUri, Sha256Digest
from jacobian.contracts.results import ContractModel


class ConjectureLicenseClass(StrEnum):
    CC0_1_0 = "CC0-1.0"
    CC_BY_4_0 = "CC-BY-4.0"
    APACHE_2_0 = "Apache-2.0"
    MIT = "MIT"
    CC_BY_NC_4_0 = "CC-BY-NC-4.0"
    CC_BY_ND_4_0 = "CC-BY-ND-4.0"
    RESTRICTED = "RESTRICTED"
    PROPRIETARY = "PROPRIETARY"
    UNKNOWN = "UNKNOWN"
    MISSING = "MISSING"


class ConjectureLicenseDecision(StrEnum):
    ALLOW_TEXT = "ALLOW_TEXT"
    METADATA_ONLY = "METADATA_ONLY"


class ExternalConjectureMetadata(ContractModel):
    title: str = Field(min_length=1, max_length=2_000)
    domain: str | None = Field(default=None, max_length=256)
    source_name: str | None = Field(default=None, max_length=512)
    source_item_url: str | None = Field(default=None, max_length=2_000)


class ExternalConjectureIngestRequest(ContractModel):
    corpus_id: str = Field(min_length=1, max_length=256)
    corpus_revision: str = Field(min_length=7, max_length=128)
    source_url: str = Field(min_length=1, max_length=2_000)
    item_id: str = Field(min_length=1, max_length=512)
    metadata: ExternalConjectureMetadata
    statement: str | None = Field(default=None, min_length=1, max_length=120_000)
    source_license: ConjectureLicenseClass
    license_evidence_url: str | None = Field(default=None, max_length=2_000)
    license_evidence_text: str | None = Field(default=None, max_length=20_000)
    license_evidence_digest: Sha256Digest | None = None
    policy_id: Literal["jacobian.external-conjecture-publication/v1"] = (
        "jacobian.external-conjecture-publication/v1"
    )
    expected_record_digest: Sha256Digest | None = None
    expected_content_digest: Sha256Digest | None = None


class ExternalConjectureIngestArtifact(ContractModel):
    artifact_version: Literal["1"] = "1"
    corpus_id: str
    corpus_revision: str
    source_url: str
    item_id: str
    metadata: ExternalConjectureMetadata
    record_digest: Sha256Digest
    supplied_content_digest: Sha256Digest | None
    indexed_content_digest: Sha256Digest | None
    source_license: ConjectureLicenseClass
    license_evidence_url: str | None
    license_evidence_digest: Sha256Digest | None
    policy_id: Literal["jacobian.external-conjecture-publication/v1"]
    license_decision: ConjectureLicenseDecision
    license_reason: str
    indexed_statement: str | None
    withheld_fields: tuple[Literal["statement"], ...]
    ingestion_status: Literal["INDEXED", "METADATA_INDEXED_TEXT_WITHHELD"]
    assurance: Literal["HEURISTIC"] = "HEURISTIC"
    verification: Literal["UNVERIFIED"] = "UNVERIFIED"


class ExternalConjectureIngestOutput(ExternalConjectureIngestArtifact):
    artifact_uri: ArtifactUri
