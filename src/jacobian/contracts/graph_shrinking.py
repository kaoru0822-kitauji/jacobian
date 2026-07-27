"""Contracts for preservation-checked shrinking of simple graph counterexamples."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, StrictBool, StrictInt, model_validator

from jacobian.contracts.common import ArtifactUri, CheckerUri
from jacobian.contracts.results import ContractModel, ExecutionStatus


class GraphReduction(StrEnum):
    DELETE_VERTEX = "delete_vertex"
    DELETE_EDGE = "delete_edge"


class GraphReductionOutcome(StrEnum):
    ACCEPTED_VERIFIED = "ACCEPTED_VERIFIED"
    PROPERTY_REJECTED = "PROPERTY_REJECTED"
    CHECKER_ERROR = "CHECKER_ERROR"
    INVALID_REDUCTION = "INVALID_REDUCTION"


class GraphCounterexampleShrinkRequest(ContractModel):
    graph_uri: ArtifactUri
    property_id: Literal["graph.property.non_bipartite"]
    property_checker_id: CheckerUri
    reducers: tuple[GraphReduction, ...] = (
        GraphReduction.DELETE_VERTEX,
        GraphReduction.DELETE_EDGE,
    )
    evaluation_budget: StrictInt = Field(ge=1, le=100_000)
    reducer_timeout_seconds: StrictInt = Field(default=30, ge=1, le=30)

    @model_validator(mode="after")
    def require_unique_reducers(self) -> Self:
        if not self.reducers:
            raise ValueError("at least one graph reducer is required")
        if len(set(self.reducers)) != len(self.reducers):
            raise ValueError("graph reducers must be unique")
        return self


class GraphReductionAttempt(ContractModel):
    index: StrictInt = Field(ge=0)
    reducer: GraphReduction
    from_graph_uri: ArtifactUri
    proposed_graph_uri: ArtifactUri | None = None
    deleted_vertex: str | None = None
    deleted_edge: tuple[str, str] | None = None
    outcome: GraphReductionOutcome
    verification_record_uri: ArtifactUri | None = None
    detail: str

    @model_validator(mode="after")
    def require_one_deletion_target(self) -> Self:
        targets = int(self.deleted_vertex is not None) + int(
            self.deleted_edge is not None
        )
        if self.proposed_graph_uri is not None and targets != 1:
            raise ValueError("a graph reduction proposal must identify one deletion")
        if self.outcome is GraphReductionOutcome.ACCEPTED_VERIFIED:
            if self.verification_record_uri is None:
                raise ValueError("an accepted reduction requires verification evidence")
        elif self.verification_record_uri is not None:
            raise ValueError("only accepted reductions may bind verification evidence")
        return self


class GraphLocalMinimalityScope(ContractModel):
    scope_kind: Literal["TESTED_SINGLE_DELETIONS"] = "TESTED_SINGLE_DELETIONS"
    requested_reducers: tuple[GraphReduction, ...]
    tested_vertex_deletions: tuple[str, ...] = ()
    tested_edge_deletions: tuple[tuple[str, str], ...] = ()
    untested_vertex_deletions: tuple[str, ...] = ()
    untested_edge_deletions: tuple[tuple[str, str], ...] = ()
    complete_for_requested_reducers: StrictBool
    one_step_locally_minimal: StrictBool
    global_minimality_claimed: Literal[False] = False
    basis: str

    @model_validator(mode="after")
    def keep_scope_claim_fail_closed(self) -> Self:
        if self.one_step_locally_minimal and not self.complete_for_requested_reducers:
            raise ValueError("local minimality requires complete requested scope")
        if self.complete_for_requested_reducers and (
            self.untested_vertex_deletions or self.untested_edge_deletions
        ):
            raise ValueError("complete scope cannot contain untested deletions")
        return self


class GraphShrinkTraceArtifact(ContractModel):
    trace_schema_version: Literal["1"] = "1"
    property_id: Literal["graph.property.non_bipartite"]
    property_checker_id: CheckerUri
    claim_uri: ArtifactUri
    initial_graph_uri: ArtifactUri
    final_graph_uri: ArtifactUri
    reducers: tuple[GraphReduction, ...]
    evaluation_budget: StrictInt = Field(ge=1)
    execution_status: ExecutionStatus
    attempts: tuple[GraphReductionAttempt, ...]
    local_minimality_scope: GraphLocalMinimalityScope


class GraphCounterexampleShrinkOutput(ContractModel):
    property_id: Literal["graph.property.non_bipartite"]
    property_checker_id: CheckerUri
    claim_uri: ArtifactUri
    initial_graph_uri: ArtifactUri
    final_graph_uri: ArtifactUri
    trace_uri: ArtifactUri
    attempts: tuple[GraphReductionAttempt, ...]
    local_minimality_scope: GraphLocalMinimalityScope
    assurance: Literal["COMPUTED_WITH_VERIFIED_ACCEPTED_STEPS"] = (
        "COMPUTED_WITH_VERIFIED_ACCEPTED_STEPS"
    )
    global_minimality_claimed: Literal[False] = False
