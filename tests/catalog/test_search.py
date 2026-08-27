from __future__ import annotations

from jacobian.catalog.catalog import Catalog
from jacobian.catalog.models import (
    OperationDescriptor,
    OperationDiscoveryMatch,
    OperationDiscoveryRequest,
)
from jacobian.catalog.search import discovery_relevance

_CONTAINMENT_PROFILE_ID = "incidence.containment_profiles.compute"


def _top_operation_ids(query: str) -> tuple[str, ...]:
    result = Catalog.open().search(OperationDiscoveryRequest(query=query, limit=5))
    return tuple(match.operation_id for match in result.matches)


def test_discovery_phrase_matching_respects_token_boundaries() -> None:
    descriptor = OperationDescriptor(
        operation_id="fixture.text.inspect",
        title="Inspect text",
        description="Inspect some paragraph of structured text.",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    graph_score = discovery_relevance(descriptor, "graph")
    phrase_score = discovery_relevance(
        descriptor,
        "paragraph of structured text",
    )

    assert graph_score == 0
    assert phrase_score >= 20


def test_standard_det_abbreviation_ranks_determinants_before_charpolys() -> None:
    catalog = Catalog.open()
    cursor: str | None = None
    matches: list[OperationDiscoveryMatch] = []
    while True:
        result = catalog.search(
            OperationDiscoveryRequest(query="det", limit=20, cursor=cursor)
        )
        matches.extend(result.matches)
        if result.next_cursor is None:
            break
        cursor = result.next_cursor

    positions = {match.operation_id: index for index, match in enumerate(matches)}

    determinant_ids = (
        "matrix.determinant.compute",
        "matrix.symbolic.determinant.compute",
    )
    characteristic_polynomial_ids = (
        "matrix.characteristic_polynomial.compute",
        "matrix.symbolic.characteristic_polynomial.compute",
    )
    assert set(determinant_ids) <= positions.keys()
    assert set(characteristic_polynomial_ids) <= positions.keys()
    assert all(
        positions[determinant_id] < positions[characteristic_polynomial_id]
        for determinant_id in determinant_ids
        for characteristic_polynomial_id in characteristic_polynomial_ids
    )


def test_t_codegree_queries_rank_the_existing_containment_profile_first() -> None:
    for query in (
        "compute t-codegrees of a finite hypergraph",
        "uniform codegree profile",
    ):
        assert _top_operation_ids(query)[0] == _CONTAINMENT_PROFILE_ID


def test_containment_language_still_ranks_the_profile_first() -> None:
    assert (
        _top_operation_ids(
            "containment counts for every pair of points in an incidence structure"
        )[0]
        == _CONTAINMENT_PROFILE_ID
    )


def test_graph_vertex_degree_query_does_not_select_a_codegree_profile() -> None:
    operation_ids = _top_operation_ids("vertex degree of a graph")

    assert "graph.realization.check.compute" in operation_ids
    assert _CONTAINMENT_PROFILE_ID not in operation_ids


def test_containment_profile_example_names_complete_pair_codegrees() -> None:
    operation = Catalog.open().operation(_CONTAINMENT_PROFILE_ID)

    assert operation is not None
    assert operation.examples[0].name == "triangle_pair_codegrees"
    assert operation.examples[0].input["t"] == 2
    assert "all pairs" in operation.examples[0].description
    assert "zero codegree" in operation.examples[0].description
