"""Typed contracts for finite simple-graph invariants."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, StrictBool, StrictInt, model_validator

from jacobian.contracts.graph_coloring import ChromaticGraph, GraphVertex
from jacobian.contracts.graph_optimization import (
    OptimizationSearchStep,
    OptimizationStatus,
    OptimizationTermination,
)
from jacobian.contracts.results import ContractModel


class GraphInvariantRequest(ContractModel):
    graph: ChromaticGraph


class GraphGirthResult(ContractModel):
    girth: StrictInt = Field(ge=0, le=32)
    has_cycle: StrictBool

    @model_validator(mode="after")
    def bind_cycle_status(self) -> Self:
        if self.has_cycle != (self.girth > 0):
            raise ValueError("has_cycle must agree with the girth sentinel")
        return self


class GraphDiameterResult(ContractModel):
    diameter: StrictInt = Field(ge=-1, le=31)
    connected: StrictBool

    @model_validator(mode="after")
    def bind_connectivity(self) -> Self:
        if self.connected == (self.diameter < 0):
            raise ValueError("diameter -1 is reserved for disconnected graphs")
        return self


class GraphEdgeConnectivityResult(ContractModel):
    edge_connectivity: StrictInt = Field(ge=0, le=31)


class GraphVertexConnectivityResult(ContractModel):
    vertex_connectivity: StrictInt = Field(ge=0, le=31)


class GraphEulerianResult(ContractModel):
    is_eulerian: StrictBool


class GraphSpanningTreeCountResult(ContractModel):
    spanning_tree_count: StrictInt = Field(ge=0)
    connected: StrictBool


class GraphMaximumMatchingResult(ContractModel):
    maximum_matching_cardinality: StrictInt = Field(ge=0, le=16)
    witness_edges: tuple[tuple[GraphVertex, GraphVertex], ...]

    @model_validator(mode="after")
    def bind_witness(self) -> Self:
        if len(self.witness_edges) != self.maximum_matching_cardinality:
            raise ValueError("matching witness cardinality must match the result")
        if (
            any(left >= right for left, right in self.witness_edges)
            or tuple(sorted(self.witness_edges)) != self.witness_edges
            or len({vertex for edge in self.witness_edges for vertex in edge})
            != 2 * len(self.witness_edges)
        ):
            raise ValueError("matching witness must be canonical and vertex-disjoint")
        return self


class GraphCardinalityMaximumResult(ContractModel):
    status: OptimizationStatus
    order: StrictInt = Field(ge=0, le=32)
    optimum_value: StrictInt | None = Field(default=None, ge=0, le=32)
    incumbent_value: StrictInt = Field(ge=0, le=32)
    lower_bound: StrictInt = Field(ge=0, le=32)
    upper_bound: StrictInt = Field(ge=0, le=32)
    witness_vertices: tuple[GraphVertex, ...]
    tested: tuple[OptimizationSearchStep, ...]
    termination_reason: OptimizationTermination
    detail: str = Field(min_length=1, max_length=1024)

    @model_validator(mode="after")
    def bind_claim_and_witness(self) -> Self:
        if self.incumbent_value != len(self.witness_vertices):
            raise ValueError("witness cardinality must match the incumbent")
        if tuple(sorted(self.witness_vertices)) != self.witness_vertices:
            raise ValueError("witness vertices must be canonically sorted")
        if self.lower_bound != self.incumbent_value:
            raise ValueError("a maximum-search incumbent is the lower bound")
        if self.status == "EXACT":
            if (
                self.optimum_value is None
                or self.lower_bound != self.optimum_value
                or self.upper_bound != self.optimum_value
            ):
                raise ValueError("exact result must bind one coincident optimum")
        elif self.optimum_value is not None:
            raise ValueError("incomplete search cannot claim an optimum")
        return self


class GraphCliqueNumberResult(GraphCardinalityMaximumResult):
    convention: Literal["MAXIMUM_COMPLETE_VERTEX_SUBSET"] = (
        "MAXIMUM_COMPLETE_VERTEX_SUBSET"
    )


class GraphIndependenceNumberResult(GraphCardinalityMaximumResult):
    convention: Literal["MAXIMUM_EDGE_FREE_VERTEX_SUBSET"] = (
        "MAXIMUM_EDGE_FREE_VERTEX_SUBSET"
    )


class GraphCardinalityMaximumObligation(ContractModel):
    obligation_schema_version: Literal["1"] = "1"
    graph: ChromaticGraph
    predicate: Literal[
        "GRAPH_CLIQUE_NUMBER_OPTIMALITY",
        "GRAPH_INDEPENDENCE_NUMBER_OPTIMALITY",
    ]
    status: OptimizationStatus
    claimed_value: StrictInt | None = Field(default=None, ge=0, le=32)
    lower_bound: StrictInt = Field(ge=0, le=32)
    upper_bound: StrictInt = Field(ge=0, le=32)
    witness_vertices: tuple[GraphVertex, ...]
    tested: tuple[OptimizationSearchStep, ...]
    required_checks: tuple[
        Literal["WITNESS_FEASIBILITY", "MAXIMUM_CARDINALITY"],
        ...,
    ] = ("WITNESS_FEASIBILITY", "MAXIMUM_CARDINALITY")
