"""Shared wire contracts for domain operations."""

from __future__ import annotations

from jacobian.contracts.common import ArtifactUri
from jacobian.contracts.results import ContractModel


class ComputedOperationOutput[ResultT: ContractModel](ContractModel):
    """Artifact-linked output whose mathematical value remains domain typed."""

    input_uri: ArtifactUri
    result_uri: ArtifactUri
    result: ResultT
    backend_version: str
