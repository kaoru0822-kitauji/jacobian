"""Contracts for untrusted representation changes and independent replay."""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from jacobian.canonical import canonicalize_json
from jacobian.contracts.common import ArtifactUri, CheckerUri, Sha256Digest
from jacobian.contracts.evidence import FormatIdentifier
from jacobian.contracts.results import (
    Arithmetic,
    Conclusion,
    ContractModel,
    Coverage,
    Method,
    ResultEnvelope,
)


class TransformationRelation(StrEnum):
    EQUIVALENT = "EQUIVALENT"
    OVER_APPROXIMATION = "OVER_APPROXIMATION"
    UNDER_APPROXIMATION = "UNDER_APPROXIMATION"
    HEURISTIC = "HEURISTIC"


class TransformationBindings(ContractModel):
    source_digest: Sha256Digest
    source_schema_uri: ArtifactUri
    source_semantics_digest: Sha256Digest
    target_digest: Sha256Digest
    target_schema_uri: ArtifactUri
    target_semantics_digest: Sha256Digest


class PluginTransformationResponse(ContractModel):
    response_version: Literal["1"] = "1"
    transform_format: FormatIdentifier
    format_version: str = Field(min_length=1, max_length=64)
    relation: TransformationRelation
    target_payload: Any
    obligation: Any
    detail: str = ""

    @model_validator(mode="after")
    def require_canonical_data(self) -> Self:
        canonicalize_json(self.target_payload)
        canonicalize_json(self.obligation)
        return self


class TransformationClaim(ContractModel):
    claim_schema_version: Literal["1"] = "1"
    transform_format: FormatIdentifier
    format_version: str
    relation: TransformationRelation
    bindings: TransformationBindings


class TransformationEnvelope(ContractModel):
    transformation_schema_version: Literal["1"] = "1"
    claim_uri: ArtifactUri
    source_uri: ArtifactUri
    target_uri: ArtifactUri
    transform_format: FormatIdentifier
    format_version: str = Field(min_length=1, max_length=64)
    relation: TransformationRelation
    bindings: TransformationBindings
    transformer_digest: Sha256Digest
    obligation_digest: Sha256Digest
    obligation: Any

    @model_validator(mode="after")
    def obligation_matches_digest(self) -> Self:
        computed = (
            "sha256:" + hashlib.sha256(canonicalize_json(self.obligation)).hexdigest()
        )
        if computed != self.obligation_digest:
            raise ValueError("transformation obligation digest does not match")
        return self


class TransformationApplyResult(ContractModel):
    schema_version: Literal["1"] = "1"
    source_uri: ArtifactUri
    target_uri: ArtifactUri | None = None
    claim_uri: ArtifactUri | None = None
    transformation_uri: ArtifactUri | None = None
    relation: TransformationRelation | None = None
    result: ResultEnvelope


class TransformationVerificationRecord(ContractModel):
    record_schema_version: Literal["1"] = "1"
    checker_id: CheckerUri
    checker_digest: Sha256Digest
    transformation_uri: ArtifactUri
    claim_uri: ArtifactUri
    bindings: TransformationBindings
    relation: TransformationRelation
    conclusion: Conclusion
    arithmetic: Arithmetic
    method: Method
    coverage: Coverage
    request_digest: Sha256Digest
    environment_digest: Sha256Digest
