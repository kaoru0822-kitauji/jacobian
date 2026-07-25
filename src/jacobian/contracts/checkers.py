"""Operator-managed checker registry contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import model_validator

from jacobian.contracts.capabilities import CapabilityId
from jacobian.contracts.common import ArtifactUri, CheckerUri, Sha256Digest
from jacobian.contracts.evidence import FormatIdentifier
from jacobian.contracts.plugins import Entrypoint
from jacobian.contracts.results import (
    Arithmetic,
    Conclusion,
    ContractModel,
    Coverage,
    Method,
)


class EvidenceKind(StrEnum):
    WITNESS = "WITNESS"
    CERTIFICATE = "CERTIFICATE"
    PRESERVATION = "PRESERVATION"
    TRANSFORMATION = "TRANSFORMATION"


class CheckerRegistration(ContractModel):
    checker_schema_version: Literal["1"] = "1"
    checker_id: CheckerUri
    name: str
    entrypoint: Entrypoint
    executable_digest: Sha256Digest
    evidence_kind: EvidenceKind
    format_id: FormatIdentifier
    format_version: str
    claim_schema_uris: tuple[ArtifactUri, ...] = ()
    semantics_uris: tuple[ArtifactUri, ...] = ()
    candidate_schema_uris: tuple[ArtifactUri, ...] = ()
    target_schema_uris: tuple[ArtifactUri, ...] = ()
    target_semantics_uris: tuple[ArtifactUri, ...] = ()
    authorized: bool = True


class CheckerAuditEvent(ContractModel):
    sequence: int
    checker_id: CheckerUri
    action: Literal["AUTHORIZED", "REVOKED"]
    reason: str
    recorded_at: str


class CheckerDecision(ContractModel):
    accepted: bool
    conclusion: Conclusion
    arithmetic: Arithmetic
    method: Method
    coverage: Coverage
    detail: str = ""
    relation_id: CapabilityId | None = None
    obligation_uri: ArtifactUri | None = None

    @model_validator(mode="after")
    def rejected_evidence_has_no_mathematical_conclusion(self) -> Self:
        if not self.accepted and self.conclusion not in {
            Conclusion.UNKNOWN,
            Conclusion.NOT_APPLICABLE,
        }:
            raise ValueError("a rejected checker input cannot decide the claim")
        if not self.accepted and (
            self.relation_id is not None or self.obligation_uri is not None
        ):
            raise ValueError("rejected evidence cannot certify relationship metadata")
        if self.accepted:
            if self.conclusion not in {Conclusion.TRUE, Conclusion.FALSE}:
                raise ValueError(
                    "accepted checker evidence requires a decisive conclusion"
                )
            if self.arithmetic == Arithmetic.FLOATING_HEURISTIC:
                raise ValueError("a checker cannot accept floating heuristic evidence")
            if self.coverage in {Coverage.RESTRICTED, Coverage.SAMPLED}:
                raise ValueError(
                    "a checker cannot accept restricted or sampled evidence"
                )
            if (
                self.method == Method.DIRECT_WITNESS
                and self.coverage != Coverage.NOT_APPLICABLE
            ):
                raise ValueError("a direct witness checker cannot claim coverage")
            if (
                self.method == Method.EXHAUSTIVE_FINITE
                and self.coverage != Coverage.EXHAUSTIVE
            ):
                raise ValueError(
                    "exhaustive checker acceptance requires exhaustive coverage"
                )
        return self
