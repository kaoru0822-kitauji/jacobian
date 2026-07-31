"""Five bounded exact finite-graph optimization operations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, cast

from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.contracts.graph_coloring import ChromaticGraph
from jacobian.contracts.graph_optimization import (
    GraphDominationMinimumObligation,
    GraphDominationMinimumOutput,
    GraphInducedBipartiteMaximumObligation,
    GraphInducedBipartiteMaximumOutput,
    GraphInducedForestMaximumObligation,
    GraphInducedForestMaximumOutput,
    GraphInducedTreeMaximumObligation,
    GraphInducedTreeMaximumOutput,
    GraphMinimumMaximalMatchingObligation,
    GraphMinimumMaximalMatchingOutput,
    GraphOptimizationBudget,
    GraphOptimizationRequest,
)
from jacobian.contracts.results import ContractModel, ExecutionStatus
from jacobian.domains.graph_optimization.exact_search import (
    solve_domination,
    solve_induced_bipartite,
    solve_induced_forest,
    solve_induced_tree,
    solve_minimum_maximal_matching,
)
from jacobian.domains.graph_optimization.operations import build_simple_graph
from jacobian.operations import (
    BoundedSearchIncomplete,
    BoundedSearchInterrupted,
    BoundedSearchOperation,
    BoundedSearchOutcome,
    BoundedSearchWitness,
    OperationExecutionFailure,
)


class _HasStatus(Protocol):
    status: str
    termination_reason: str


def _valid_witness(graph: Any, result: ContractModel) -> bool:
    import networkx as nx

    graph_vertices = set(graph)
    if isinstance(result, GraphDominationMinimumOutput):
        return set(result.witness_vertices) <= graph_vertices and nx.is_dominating_set(
            graph,
            result.witness_vertices,
        )
    if isinstance(result, GraphMinimumMaximalMatchingOutput):
        edges = set(result.witness_edges)
        return (
            all(
                left in graph_vertices and right in graph_vertices
                for left, right in edges
            )
            and nx.is_matching(graph, edges)
            and nx.is_maximal_matching(graph, edges)
        )
    if isinstance(result, GraphInducedForestMaximumOutput):
        if not set(result.witness_vertices) <= graph_vertices:
            return False
        induced = graph.subgraph(result.witness_vertices)
        return induced.number_of_nodes() == 0 or nx.is_forest(induced)
    if isinstance(result, GraphInducedTreeMaximumOutput):
        if not set(result.witness_vertices) <= graph_vertices:
            return False
        induced = graph.subgraph(result.witness_vertices)
        return (graph.number_of_nodes() == 0 and induced.number_of_nodes() == 0) or (
            induced.number_of_nodes() > 0
            and nx.is_connected(induced)
            and nx.is_forest(induced)
        )
    if isinstance(result, GraphInducedBipartiteMaximumOutput):
        return set(result.witness_vertices) <= graph_vertices and nx.is_bipartite(
            graph.subgraph(result.witness_vertices)
        )
    return False


_INVALID_GRAPH_OPTIMIZATION_REQUEST = CapabilityDiagnostic(
    code="INVALID_GRAPH_OPTIMIZATION_REQUEST",
    stage="graph_optimization_input_validation",
    message="Input does not satisfy the bounded finite-graph optimization contract.",
    hint=(
        "Supply a canonical finite simple graph within max_order and explicit "
        "wall-clock and solver-call budgets."
    ),
)


def _execute[ResultT: ContractModel](
    request: GraphOptimizationRequest,
    solve: Callable[
        [Any, ChromaticGraph, GraphOptimizationBudget],
        ResultT,
    ],
) -> BoundedSearchOutcome[ResultT]:
    graph = cast(Any, build_simple_graph(request.graph))
    result = solve(graph, request.graph, request.resource_budget)
    state = cast(_HasStatus, result)
    if not _valid_witness(graph, result):
        return OperationExecutionFailure(
            status=ExecutionStatus.ERROR,
            diagnostic=CapabilityDiagnostic(
                code="GRAPH_OPTIMIZATION_WITNESS_INVALID",
                stage="graph_optimization_postcondition",
                message=(
                    "The solver returned an incumbent that does not satisfy "
                    "the declared graph predicate."
                ),
            ),
        )
    if state.status == "EXACT":
        return BoundedSearchWitness(result)
    if state.termination_reason in {"WALL_TIME", "SOLVER_UNKNOWN"}:
        return BoundedSearchInterrupted(
            value=result,
            status=ExecutionStatus.TIMEOUT,
            diagnostic=CapabilityDiagnostic(
                code="GRAPH_OPTIMIZATION_TIMEOUT",
                stage="graph_optimization_search",
                message=(
                    "The graph optimization search exhausted its wall-clock "
                    "budget before establishing optimality."
                ),
            ),
        )
    return BoundedSearchIncomplete(result)


def _scope(
    request: GraphOptimizationRequest,
    result: ContractModel,
) -> dict[str, object]:
    del result
    return {
        "order": len(request.graph.vertices),
        "wall_seconds": request.resource_budget.wall_seconds,
        "max_solver_calls": request.resource_budget.max_solver_calls,
        "max_order": request.resource_budget.max_order,
    }


def _vertex_obligation[ObligationT: ContractModel](
    request: GraphOptimizationRequest,
    result: (
        GraphDominationMinimumOutput
        | GraphInducedForestMaximumOutput
        | GraphInducedTreeMaximumOutput
        | GraphInducedBipartiteMaximumOutput
    ),
    model: type[ObligationT],
) -> ObligationT:
    return model.model_validate(
        {
            "graph": request.graph,
            "status": result.status,
            "claimed_value": result.optimum_value,
            "lower_bound": result.lower_bound,
            "upper_bound": result.upper_bound,
            "witness_vertices": result.witness_vertices,
            "tested": result.tested,
        }
    )


def _matching_obligation(
    request: GraphOptimizationRequest,
    result: GraphMinimumMaximalMatchingOutput,
) -> GraphMinimumMaximalMatchingObligation:
    return GraphMinimumMaximalMatchingObligation(
        graph=request.graph,
        status=result.status,
        claimed_value=result.optimum_value,
        lower_bound=result.lower_bound,
        upper_bound=result.upper_bound,
        witness_edges=result.witness_edges,
        tested=result.tested,
    )


DOMINATION_MINIMUM_CAPABILITY = BoundedSearchOperation(
    capability_id="graph.domination.minimum.compute",
    title="Minimum dominating set",
    description=(
        "Compute the ordinary domination number and an attaining set under "
        "explicit order, solver-call, and wall-clock budgets."
    ),
    request_model=GraphOptimizationRequest,
    result_model=GraphDominationMinimumOutput,
    implementation=lambda request: _execute(request, solve_domination),
    relation_id="graph.domination.minimum.relation",
    scope_parameters=_scope,
    is_complete=lambda result: result.status == "EXACT",
    obligation_model=GraphDominationMinimumObligation,
    obligation=lambda request, result: _vertex_obligation(
        request, result, GraphDominationMinimumObligation
    ),
    incomplete_basis="the bounded threshold search did not establish optimality",
    tags=("graph", "domination", "minimum", "bounded", "z3"),
    invalid_request=_INVALID_GRAPH_OPTIMIZATION_REQUEST,
)

MINIMUM_MAXIMAL_MATCHING_CAPABILITY = BoundedSearchOperation(
    capability_id="graph.matching.maximal.minimum.compute",
    title="Minimum maximal matching",
    description=(
        "Compute the saturation number and an attaining maximal matching under "
        "explicit order, solver-call, and wall-clock budgets."
    ),
    request_model=GraphOptimizationRequest,
    result_model=GraphMinimumMaximalMatchingOutput,
    implementation=lambda request: _execute(request, solve_minimum_maximal_matching),
    relation_id="graph.matching.maximal.minimum.relation",
    scope_parameters=_scope,
    is_complete=lambda result: result.status == "EXACT",
    obligation_model=GraphMinimumMaximalMatchingObligation,
    obligation=_matching_obligation,
    incomplete_basis="the bounded threshold search did not establish optimality",
    tags=("graph", "matching", "saturation_number", "minimum", "bounded", "z3"),
    invalid_request=_INVALID_GRAPH_OPTIMIZATION_REQUEST,
)

INDUCED_FOREST_MAXIMUM_CAPABILITY = BoundedSearchOperation(
    capability_id="graph.induced_forest.maximum.compute",
    title="Maximum induced forest",
    description=(
        "Compute a maximum-order induced forest and its vertex witness under "
        "explicit order, solver-call, and wall-clock budgets."
    ),
    request_model=GraphOptimizationRequest,
    result_model=GraphInducedForestMaximumOutput,
    implementation=lambda request: _execute(request, solve_induced_forest),
    relation_id="graph.induced_forest.maximum.relation",
    scope_parameters=_scope,
    is_complete=lambda result: result.status == "EXACT",
    obligation_model=GraphInducedForestMaximumObligation,
    obligation=lambda request, result: _vertex_obligation(
        request, result, GraphInducedForestMaximumObligation
    ),
    incomplete_basis="the bounded threshold search did not establish optimality",
    tags=("graph", "induced_forest", "maximum", "bounded", "z3"),
    invalid_request=_INVALID_GRAPH_OPTIMIZATION_REQUEST,
)

INDUCED_TREE_MAXIMUM_CAPABILITY = BoundedSearchOperation(
    capability_id="graph.induced_tree.maximum.compute",
    title="Maximum induced tree",
    description=(
        "Compute a maximum-order nonempty connected acyclic induced subgraph "
        "under explicit order, solver-call, and wall-clock budgets."
    ),
    request_model=GraphOptimizationRequest,
    result_model=GraphInducedTreeMaximumOutput,
    implementation=lambda request: _execute(request, solve_induced_tree),
    relation_id="graph.induced_tree.maximum.relation",
    scope_parameters=_scope,
    is_complete=lambda result: result.status == "EXACT",
    obligation_model=GraphInducedTreeMaximumObligation,
    obligation=lambda request, result: _vertex_obligation(
        request, result, GraphInducedTreeMaximumObligation
    ),
    incomplete_basis="the bounded threshold search did not establish optimality",
    tags=("graph", "induced_tree", "maximum", "bounded", "z3"),
    invalid_request=_INVALID_GRAPH_OPTIMIZATION_REQUEST,
)

INDUCED_BIPARTITE_MAXIMUM_CAPABILITY = BoundedSearchOperation(
    capability_id="graph.induced_bipartite.maximum.compute",
    title="Maximum induced bipartite subgraph",
    description=(
        "Compute a maximum-order induced bipartite subgraph and its vertex "
        "witness under explicit order, solver-call, and wall-clock budgets."
    ),
    request_model=GraphOptimizationRequest,
    result_model=GraphInducedBipartiteMaximumOutput,
    implementation=lambda request: _execute(request, solve_induced_bipartite),
    relation_id="graph.induced_bipartite.maximum.relation",
    scope_parameters=_scope,
    is_complete=lambda result: result.status == "EXACT",
    obligation_model=GraphInducedBipartiteMaximumObligation,
    obligation=lambda request, result: _vertex_obligation(
        request, result, GraphInducedBipartiteMaximumObligation
    ),
    incomplete_basis="the bounded threshold search did not establish optimality",
    tags=("graph", "induced_bipartite", "maximum", "bounded", "z3"),
    invalid_request=_INVALID_GRAPH_OPTIMIZATION_REQUEST,
)

FINITE_GRAPH_OPTIMIZATION_CAPABILITIES = (
    DOMINATION_MINIMUM_CAPABILITY,
    MINIMUM_MAXIMAL_MATCHING_CAPABILITY,
    INDUCED_FOREST_MAXIMUM_CAPABILITY,
    INDUCED_TREE_MAXIMUM_CAPABILITY,
    INDUCED_BIPARTITE_MAXIMUM_CAPABILITY,
)
