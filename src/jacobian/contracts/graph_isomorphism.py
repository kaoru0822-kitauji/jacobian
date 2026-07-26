"""Direct finite-graph isomorphism verification contracts."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from jacobian.contracts.common import ArtifactUri, CheckerUri
from jacobian.contracts.graph_invariants import GraphVertex
from jacobian.contracts.results import ContractModel


class SimpleUndirectedGraph(ContractModel):
    graph_schema_version: Literal["1"] = "1"
    vertices: tuple[GraphVertex, ...] = Field(max_length=256)
    edges: tuple[tuple[GraphVertex, GraphVertex], ...] = Field(max_length=32640)

    @model_validator(mode="after")
    def require_canonical_simple_graph(self) -> Self:
        if self.vertices != tuple(sorted(set(self.vertices))):
            raise ValueError("graph vertices must be unique and sorted")
        if any(
            left >= right or left not in self.vertices or right not in self.vertices
            for left, right in self.edges
        ):
            raise ValueError("edges must contain two declared vertices in order")
        if self.edges != tuple(sorted(set(self.edges))):
            raise ValueError("graph edges must be unique and sorted")
        return self


class GraphPair(ContractModel):
    pair_schema_version: Literal["1"] = "1"
    left: SimpleUndirectedGraph
    right: SimpleUndirectedGraph


class GraphVertexMapping(ContractModel):
    mapping_schema_version: Literal["1"] = "1"
    mapping: dict[GraphVertex, GraphVertex] = Field(max_length=256)


class GraphIsomorphismVerifyRequest(ContractModel):
    left: SimpleUndirectedGraph
    right: SimpleUndirectedGraph
    mapping: dict[GraphVertex, GraphVertex] = Field(max_length=256)


class GraphIsomorphismClaim(ContractModel):
    claim_schema_version: Literal["1"] = "1"
    predicate: Literal["MAPPING_IS_GRAPH_ISOMORPHISM"] = "MAPPING_IS_GRAPH_ISOMORPHISM"
    graph_pair_uri: ArtifactUri
    mapping_uri: ArtifactUri


class GraphIsomorphismReplay(ContractModel):
    method: Literal["DIRECT_ADJACENCY_REPLAY"] = "DIRECT_ADJACENCY_REPLAY"
    graph_pair_uri: ArtifactUri
    mapping_uri: ArtifactUri


class GraphIsomorphismVerifyOutput(ContractModel):
    is_isomorphism: bool
    conclusion: Literal["TRUE", "FALSE", "UNKNOWN"]
    graph_pair_uri: ArtifactUri
    mapping_uri: ArtifactUri
    claim_uri: ArtifactUri
    certificate_uri: ArtifactUri
    verification_record_uri: ArtifactUri | None = None
    checker_id: CheckerUri | None = None
    coverage: Literal["EXHAUSTIVE"] = "EXHAUSTIVE"
