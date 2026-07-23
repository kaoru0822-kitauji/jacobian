"""Artifact storage wire contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from jacobian.contracts.common import ArtifactUri, Sha256Digest
from jacobian.contracts.results import ContractModel


class ArtifactManifest(ContractModel):
    manifest_version: Literal["1"] = "1"
    object_digest: Sha256Digest
    payload_digest: Sha256Digest
    schema_uri: ArtifactUri
    semantics_uri: ArtifactUri
    canonicalizer_digest: Sha256Digest
    parents: tuple[ArtifactUri, ...] = ()
    summary: str = Field(default="", max_length=512)


class ArtifactPutResult(ContractModel):
    artifact_uri: ArtifactUri
    object_digest: Sha256Digest
    manifest_digest: Sha256Digest
    canonicalizer_digest: Sha256Digest
