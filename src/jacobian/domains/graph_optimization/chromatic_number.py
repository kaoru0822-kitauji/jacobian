"""Bounded exact chromatic-number operation."""

from __future__ import annotations

from jacobian.contracts.capabilities import CapabilityDiagnostic
from jacobian.contracts.graph_coloring import (
    ChromaticNumberBudget,
    GraphChromaticNumberObligation,
    GraphChromaticNumberOutput,
    GraphChromaticNumberRequest,
)
from jacobian.contracts.results import ContractModel
from jacobian.domains.graph_optimization.operations import (
    build_simple_graph,
    solve_chromatic_number,
)
from jacobian.operations import (
    BoundedSearchIncomplete,
    BoundedSearchNotApplicable,
    BoundedSearchOperation,
    BoundedSearchOutcome,
    BoundedSearchWitness,
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

    if output.status == "EXACT":
        return BoundedSearchWitness(value=output)
    return BoundedSearchIncomplete(value=output)


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
) -> ContractModel:
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
