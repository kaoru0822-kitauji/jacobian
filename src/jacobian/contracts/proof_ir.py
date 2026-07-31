"""Bounded logical-claim artifacts for the implemented decomposition operations."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from jacobian.contracts.common import ArtifactUri, Sha256Digest
from jacobian.contracts.results import ContractModel


class AtomicClaimRef(ContractModel):
    """An immutable reference to one claim artifact and its two identities."""

    claim_artifact_uri: ArtifactUri
    schema_digest: Sha256Digest
    semantics_digest: Sha256Digest


class ConjunctionClaim(ContractModel):
    """A finite ordered conjunction of atomic claim references."""

    claim_refs: tuple[AtomicClaimRef, ...] = Field(min_length=1, max_length=256)


class ImplicationClaim(ContractModel):
    """A finite implication with explicit premises and one conclusion."""

    premises: tuple[AtomicClaimRef, ...] = Field(min_length=1, max_length=256)
    conclusion: AtomicClaimRef


LogicalClaim = AtomicClaimRef | ConjunctionClaim | ImplicationClaim


class ProofObligationSet(ContractModel):
    """Decomposition structure, not proof authority."""

    source_logical_claim: LogicalClaim
    obligation_refs: tuple[AtomicClaimRef, ...] = Field(
        min_length=1,
        max_length=256,
    )
    decomposition_semantics: Sha256Digest
    completeness_status: Literal["COMPLETE", "INCOMPLETE"]

    @model_validator(mode="after")
    def require_distinct_obligations(self) -> Self:
        uris = tuple(item.claim_artifact_uri for item in self.obligation_refs)
        if len(set(uris)) != len(uris):
            raise ValueError(
                "proof obligations must reference distinct claim artifacts"
            )
        return self


__all__ = [
    "AtomicClaimRef",
    "ConjunctionClaim",
    "ImplicationClaim",
    "LogicalClaim",
    "ProofObligationSet",
]
