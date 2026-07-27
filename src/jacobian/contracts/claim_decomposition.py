"""Bounded structured-claim and deterministic decomposition contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from jacobian.canonical import canonicalize_json
from jacobian.contracts.common import ArtifactUri, Sha256Digest
from jacobian.contracts.results import ContractModel


class LogicalConnective(StrEnum):
    ATOM = "ATOM"
    CONJUNCTION = "CONJUNCTION"
    IMPLICATION = "IMPLICATION"
    DISJUNCTION = "DISJUNCTION"
    NEGATION = "NEGATION"
    BICONDITIONAL = "BICONDITIONAL"
    QUANTIFIER = "QUANTIFIER"


class LogicalClaimNode(ContractModel):
    """One explicitly grouped logical node; unsupported kinds remain representable."""

    node_id: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_.-]*$", max_length=128)
    connective: LogicalConnective
    atom: dict[str, Any] | None = None
    children: tuple[LogicalClaimNode, ...] = ()
    source_span: tuple[int, int] | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if self.source_span is not None and self.source_span[0] > self.source_span[1]:
            raise ValueError("source_span start must not exceed its end")
        canonicalize_json(self.atom)
        expected = {
            LogicalConnective.ATOM: 0,
            LogicalConnective.IMPLICATION: 2,
            LogicalConnective.NEGATION: 1,
            LogicalConnective.BICONDITIONAL: 2,
            LogicalConnective.QUANTIFIER: 1,
        }.get(self.connective)
        if self.connective is LogicalConnective.CONJUNCTION:
            if len(self.children) < 2:
                raise ValueError("CONJUNCTION requires at least two ordered children")
        elif self.connective is LogicalConnective.DISJUNCTION:
            if len(self.children) < 2:
                raise ValueError("DISJUNCTION requires at least two ordered children")
        elif expected is not None and len(self.children) != expected:
            raise ValueError(
                f"{self.connective.value} requires exactly {expected} children"
            )
        if self.connective is LogicalConnective.ATOM:
            if self.atom is None:
                raise ValueError("ATOM requires an opaque canonical atom payload")
        elif self.atom is not None:
            raise ValueError("only ATOM may carry an atom payload")
        return self


class StructuredClaimArtifact(ContractModel):
    structured_claim_schema_version: Literal["1"] = "1"
    logic: Literal["PROPOSITIONAL_STRUCTURE"] = "PROPOSITIONAL_STRUCTURE"
    root: LogicalClaimNode

    @model_validator(mode="after")
    def enforce_bounds_and_ids(self) -> Self:
        pending = [(self.root, 1)]
        identifiers: set[str] = set()
        count = 0
        while pending:
            node, depth = pending.pop()
            count += 1
            if count > 1024:
                raise ValueError("structured claim exceeds 1024 nodes")
            if depth > 64:
                raise ValueError("structured claim exceeds depth 64")
            if node.node_id in identifiers:
                raise ValueError("structured claim node_id values must be unique")
            identifiers.add(node.node_id)
            pending.extend((child, depth + 1) for child in node.children)
        return self


class ClaimDecompositionRequest(ContractModel):
    source_uri: ArtifactUri


class SourceArtifactBinding(ContractModel):
    source_uri: ArtifactUri
    object_digest: Sha256Digest
    payload_digest: Sha256Digest
    schema_uri: ArtifactUri
    semantics_uri: ArtifactUri
    canonicalizer_digest: Sha256Digest


class DecomposedOccurrence(ContractModel):
    position: int = Field(ge=0)
    role: Literal[
        "CONJUNCT",
        "ASSUME_ANTECEDENT",
        "PROVE_CONSEQUENT_UNDER_ANTECEDENT",
    ]
    path: str
    node: LogicalClaimNode
    node_digest: Sha256Digest


class ReconstructionRecord(ContractModel):
    operator: Literal["CONJUNCTION", "IMPLICATION"]
    root_node_id: str
    root_source_span: tuple[int, int] | None = None
    source_root_digest: Sha256Digest
    ordered_child_digests: tuple[Sha256Digest, ...]


class ClaimDecompositionArtifact(ContractModel):
    decomposition_schema_version: Literal["1"] = "1"
    capability_id: Literal[
        "claim.conjunction.split",
        "claim.implication.obligations",
    ]
    source_binding: SourceArtifactBinding
    occurrences: tuple[DecomposedOccurrence, ...]
    reconstruction: ReconstructionRecord


class ClaimDecompositionOutput(ClaimDecompositionArtifact):
    decomposition_uri: ArtifactUri


LogicalClaimNode.model_rebuild()
