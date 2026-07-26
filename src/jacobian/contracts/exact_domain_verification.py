"""Contracts for independent verification of exact domain-operation results."""

from __future__ import annotations

from typing import Literal

from jacobian.contracts.capabilities import CapabilityId
from jacobian.contracts.common import ArtifactUri, CheckerUri
from jacobian.contracts.results import ContractModel


class ExactDomainResultVerificationRequest(ContractModel):
    result_uri: ArtifactUri


class ExactDomainResultVerificationOutput(ContractModel):
    status: Literal["VERIFIED", "REJECTED", "TIMEOUT", "CANCELLED", "ERROR"]
    conclusion: Literal["TRUE", "UNKNOWN"]
    operation_id: CapabilityId
    input_uri: ArtifactUri
    result_uri: ArtifactUri
    witness_uri: ArtifactUri
    checker_id: CheckerUri
    verification_record_uri: ArtifactUri | None = None
    detail: str


__all__ = [
    "ExactDomainResultVerificationOutput",
    "ExactDomainResultVerificationRequest",
]
