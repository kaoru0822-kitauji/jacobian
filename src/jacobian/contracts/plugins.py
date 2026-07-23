"""Domain-independent plugin manifest contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from jacobian.contracts.common import ArtifactUri
from jacobian.contracts.results import ContractModel

Entrypoint = Annotated[
    str,
    StringConstraints(
        pattern=r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$",
        strict=True,
    ),
]
DomainIdentifier = Annotated[
    str,
    StringConstraints(
        pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$",
        min_length=3,
        max_length=128,
        strict=True,
    ),
]


class CapabilityName(StrEnum):
    CANDIDATE_CODEC = "CandidateCodec"
    EVALUATOR = "Evaluator"
    WITNESS_ORACLE = "WitnessOracle"
    REDUCER = "Reducer"
    SEMANTIC_ENUMERATOR = "SemanticEnumerator"
    CANDIDATE_ENUMERATOR = "CandidateEnumerator"
    CANONICALIZER = "Canonicalizer"
    TRANSFORMER = "Transformer"


class CapabilityDescriptor(ContractModel):
    implementation_uri: ArtifactUri
    entrypoint: Entrypoint
    version: str = Field(default="1", min_length=1, max_length=64)


class PluginManifest(ContractModel):
    """Untrusted capabilities and immutable domain bindings.

    The artifact URI containing this model is the plugin identifier. A manifest
    deliberately has no checker-authorization field.
    """

    plugin_schema_version: Literal["1"] = "1"
    domain_id: DomainIdentifier
    domain_version: str = Field(min_length=1, max_length=64)
    semantics_uri: ArtifactUri
    claim_schema_uri: ArtifactUri
    candidate_schema_uri: ArtifactUri
    witness_schema_uris: tuple[ArtifactUri, ...] = ()
    certificate_schema_uris: tuple[ArtifactUri, ...] = ()
    capabilities: dict[CapabilityName, CapabilityDescriptor]
