"""Immutable records produced by authorized checker execution."""

from __future__ import annotations

from typing import Literal

from jacobian.contracts.capabilities import CapabilityId
from jacobian.contracts.checkers import EvidenceKind
from jacobian.contracts.common import ArtifactUri, CheckerUri, Sha256Digest
from jacobian.contracts.evidence import EvidenceBindings
from jacobian.contracts.results import (
    Arithmetic,
    Conclusion,
    ContractModel,
    Coverage,
    Method,
)


class VerificationRecord(ContractModel):
    record_schema_version: Literal["1"] = "1"
    checker_id: CheckerUri
    checker_digest: Sha256Digest
    evidence_kind: EvidenceKind
    evidence_uri: ArtifactUri
    bindings: EvidenceBindings
    conclusion: Conclusion
    arithmetic: Arithmetic
    method: Method
    coverage: Coverage
    request_digest: Sha256Digest
    environment_digest: Sha256Digest
    relation_id: CapabilityId | None = None
    obligation_uri: ArtifactUri | None = None
