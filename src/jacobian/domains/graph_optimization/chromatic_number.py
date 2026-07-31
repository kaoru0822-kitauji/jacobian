"""Bounded exact chromatic-number operation."""

from __future__ import annotations

from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.contracts.graph_coloring import (
    ChromaticNumberBudget,
    GraphChromaticNumberObligation,
    GraphChromaticNumberOutput,
    GraphChromaticNumberRequest,
)
from jacobian.contracts.results import ExecutionStatus
from jacobian.domains.graph_optimization.operations import (
    build_simple_graph,
    solve_chromatic_number,
)
from jacobian.operations import (
    BoundedSearchInterrupted,
    BoundedSearchNotApplicable,
    BoundedSearchOperation,
    BoundedSearchOutcome,
    BoundedSearchWitness,
    OperationExecutionFailure,
)


def _search_chromatic_number(
    request: GraphChromaticNumberRequest,
) -> BoundedSearchOutcome[GraphChromaticNumberOutput]:
    """Run bounded k-colorability decisions until exactness or timeout."""

    try:
        networkx_graph = build_simple_graph(request.graph)
    except (KeyError, ValueError, TypeError) as exc:
        return BoundedSearchNotApplicable(
            CapabilityDiagnostic(
                code="CHROMATIC_NUMBER_GRAPH_NOT_APPLICABLE",
                stage="graph_optimization_precondition",
                message=str(exc),
                hint="Supply a simple undirected graph with unique vertices.",
            )
        )

    output = solve_chromatic_number(
        networkx_graph,
        graph=request.graph,
        vertices=request.graph.vertices,
        wall_seconds=request.resource_budget.wall_seconds,
    )

    if (
        output.vertices != request.graph.vertices
        or output.order != len(request.graph.vertices)
        or (
            output.coloring is not None
            and (
                set(output.coloring) != set(request.graph.vertices)
                or any(
                    output.coloring[left] == output.coloring[right]
                    for left, right in request.graph.edges
                )
            )
        )
    ):
        return OperationExecutionFailure(
            status=ExecutionStatus.ERROR,
            diagnostic=CapabilityDiagnostic(
                code="CHROMATIC_NUMBER_COLORING_INVALID",
                stage="graph_optimization_postcondition",
                message="The solver returned a coloring that does not separate an edge.",
            ),
        )
    if output.status == "EXACT":
        return BoundedSearchWitness(value=output)
    return BoundedSearchInterrupted(
        value=output,
        status=ExecutionStatus.TIMEOUT,
        diagnostic=CapabilityDiagnostic(
            code="CHROMATIC_NUMBER_TIMEOUT",
            stage="graph_optimization_search",
            message=(
                "The chromatic-number search exhausted its wall-clock budget "
                "before establishing exactness."
            ),
        ),
    )


def _chromatic_number_scope_parameters(
    request: GraphChromaticNumberRequest,
    result: GraphChromaticNumberOutput,
) -> dict[str, object]:
    budget: ChromaticNumberBudget = request.resource_budget
    return {
        "wall_seconds": budget.wall_seconds,
        "order": result.order,
    }


def _chromatic_number_obligation(
    request: GraphChromaticNumberRequest,
    result: GraphChromaticNumberOutput,
) -> GraphChromaticNumberObligation:
    return GraphChromaticNumberObligation(
        graph=request.graph,
        status=result.status,
        claimed_value=result.chromatic_number,
        lower_bound=result.lower_bound,
        upper_bound=result.upper_bound,
        coloring=result.coloring,
        tested=result.tested,
    )


CHROMATIC_NUMBER_CAPABILITY = BoundedSearchOperation(
    capability_id="graph.invariant.chromatic_number.compute",
    title="Exact chromatic number",
    description=(
        "Compute the exact chromatic number of a bounded simple undirected "
        "graph by bounded Z3 k-colorability decisions. A timeout returns "
        "an UNKNOWN result with the tested bounds and search trace."
    ),
    request_model=GraphChromaticNumberRequest,
    result_model=GraphChromaticNumberOutput,
    implementation=_search_chromatic_number,
    relation_id="graph.invariant.chromatic_number.relation",
    scope_parameters=_chromatic_number_scope_parameters,
    is_complete=lambda result: result.status == "EXACT",
    obligation_model=GraphChromaticNumberObligation,
    obligation=_chromatic_number_obligation,
    incomplete_basis=(
        "the declared wall-clock budget ended before exactness was established"
    ),
    tags=(
        "graph",
        "invariant",
        "chromatic_number",
        "exact",
        "bounded",
        "z3",
    ),
)
