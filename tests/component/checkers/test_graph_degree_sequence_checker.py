from __future__ import annotations

from copy import deepcopy
from typing import Any

from jacobian_checkers.graph_degree_sequence import check_degree_sequence


def _bindings() -> dict[str, str | None]:
    return {
        "claim_digest": "sha256:" + "a" * 64,
        "semantics_digest": "sha256:" + "b" * 64,
        "candidate_digest": "sha256:" + "c" * 64,
        "scope_digest": None,
        "encoding_digest": None,
    }


def _request(
    *,
    sequence: list[int],
    candidate: dict[str, Any],
    certificate_payload: dict[str, Any],
) -> dict[str, Any]:
    bindings = _bindings()
    return {
        "request_version": "1",
        "claim": {
            "payload": {
                "claim_schema_version": "1",
                "predicate": "SIMPLE_GRAPH_DEGREE_SEQUENCE",
                "degree_sequence": sequence,
            }
        },
        "candidate": {"payload": candidate},
        "certificate": {
            "payload": {
                "evidence_schema_version": "1",
                "certificate_type": "graph.degree_sequence",
                "format_version": "1",
                "bindings": deepcopy(bindings),
                "payload_digest": "sha256:" + "d" * 64,
                "payload": certificate_payload,
            }
        },
        "expected_bindings": deepcopy(bindings),
    }


def test_checker_accepts_exact_graph_realization() -> None:
    graph_uri = "artifact://sha256/" + "1" * 64
    request = _request(
        sequence=[2, 2, 1, 1],
        candidate={
            "result_schema_version": "1",
            "degree_sequence": [2, 2, 1, 1],
            "conclusion": "GRAPHICAL",
            "graph_uri": graph_uri,
            "graph": {
                "graph_schema_version": "1",
                "vertices": ["v0", "v1", "v2", "v3"],
                "edges": [["v0", "v1"], ["v0", "v2"], ["v1", "v3"]],
            },
            "obstruction": None,
        },
        certificate_payload={
            "method": "EXACT_DEGREE_REPLAY",
            "degree_sequence": [2, 2, 1, 1],
            "conclusion": "GRAPHICAL",
            "graph_uri": graph_uri,
            "obstruction": None,
        },
    )

    decision = check_degree_sequence(request)

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"


def test_checker_rejects_mutated_realization() -> None:
    graph_uri = "artifact://sha256/" + "1" * 64
    request = _request(
        sequence=[2, 2, 1, 1],
        candidate={
            "result_schema_version": "1",
            "degree_sequence": [2, 2, 1, 1],
            "conclusion": "GRAPHICAL",
            "graph_uri": graph_uri,
            "graph": {
                "graph_schema_version": "1",
                "vertices": ["v0", "v1", "v2", "v3"],
                "edges": [["v0", "v1"], ["v0", "v2"]],
            },
            "obstruction": None,
        },
        certificate_payload={
            "method": "EXACT_DEGREE_REPLAY",
            "degree_sequence": [2, 2, 1, 1],
            "conclusion": "GRAPHICAL",
            "graph_uri": graph_uri,
            "obstruction": None,
        },
    )

    decision = check_degree_sequence(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_checker_accepts_erdos_gallai_obstruction() -> None:
    obstruction = {
        "kind": "ERDOS_GALLAI",
        "k": 2,
        "lhs": 6,
        "rhs": 4,
    }
    request = _request(
        sequence=[3, 3, 1, 1],
        candidate={
            "result_schema_version": "1",
            "degree_sequence": [3, 3, 1, 1],
            "conclusion": "NON_GRAPHICAL",
            "graph_uri": None,
            "graph": None,
            "obstruction": obstruction,
        },
        certificate_payload={
            "method": "ERDOS_GALLAI_OBSTRUCTION",
            "degree_sequence": [3, 3, 1, 1],
            "conclusion": "NON_GRAPHICAL",
            "graph_uri": None,
            "obstruction": obstruction,
        },
    )

    decision = check_degree_sequence(request)

    assert decision["accepted"] is True
    assert decision["conclusion"] == "FALSE"


def test_checker_rejects_fabricated_erdos_gallai_obstruction() -> None:
    obstruction = {
        "kind": "ERDOS_GALLAI",
        "k": 2,
        "lhs": 6,
        "rhs": 5,
    }
    request = _request(
        sequence=[3, 3, 1, 1],
        candidate={
            "result_schema_version": "1",
            "degree_sequence": [3, 3, 1, 1],
            "conclusion": "NON_GRAPHICAL",
            "graph_uri": None,
            "graph": None,
            "obstruction": obstruction,
        },
        certificate_payload={
            "method": "ERDOS_GALLAI_OBSTRUCTION",
            "degree_sequence": [3, 3, 1, 1],
            "conclusion": "NON_GRAPHICAL",
            "graph_uri": None,
            "obstruction": obstruction,
        },
    )

    decision = check_degree_sequence(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_checker_accepts_max_degree_obstruction() -> None:
    """A degree exceeding the simple-graph maximum is a valid non-graphical obstruction."""
    obstruction = {
        "kind": "MAX_DEGREE",
        "index": 0,
        "degree": 4,
        "order": 4,
    }
    request = _request(
        sequence=[4, 1, 1, 0],
        candidate={
            "result_schema_version": "1",
            "degree_sequence": [4, 1, 1, 0],
            "conclusion": "NON_GRAPHICAL",
            "graph_uri": None,
            "graph": None,
            "obstruction": obstruction,
        },
        certificate_payload={
            "method": "MAX_DEGREE_OBSTRUCTION",
            "degree_sequence": [4, 1, 1, 0],
            "conclusion": "NON_GRAPHICAL",
            "graph_uri": None,
            "obstruction": obstruction,
        },
    )

    decision = check_degree_sequence(request)

    assert decision["accepted"] is True
    assert decision["conclusion"] == "FALSE"


def test_checker_rejects_fabricated_max_degree_obstruction() -> None:
    """A MAX_DEGREE obstruction whose degree does not exceed the maximum is fabricated."""
    obstruction = {
        "kind": "MAX_DEGREE",
        "index": 0,
        "degree": 3,
        "order": 4,
    }
    request = _request(
        sequence=[3, 1, 1, 0],
        candidate={
            "result_schema_version": "1",
            "degree_sequence": [3, 1, 1, 0],
            "conclusion": "NON_GRAPHICAL",
            "graph_uri": None,
            "graph": None,
            "obstruction": obstruction,
        },
        certificate_payload={
            "method": "MAX_DEGREE_OBSTRUCTION",
            "degree_sequence": [3, 1, 1, 0],
            "conclusion": "NON_GRAPHICAL",
            "graph_uri": None,
            "obstruction": obstruction,
        },
    )

    decision = check_degree_sequence(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_checker_accepts_odd_sum_obstruction() -> None:
    """An odd degree sum is a valid non-graphical obstruction."""
    obstruction = {
        "kind": "ODD_SUM",
        "degree_sum": 7,
    }
    request = _request(
        sequence=[3, 2, 1, 1],
        candidate={
            "result_schema_version": "1",
            "degree_sequence": [3, 2, 1, 1],
            "conclusion": "NON_GRAPHICAL",
            "graph_uri": None,
            "graph": None,
            "obstruction": obstruction,
        },
        certificate_payload={
            "method": "ODD_SUM_OBSTRUCTION",
            "degree_sequence": [3, 2, 1, 1],
            "conclusion": "NON_GRAPHICAL",
            "graph_uri": None,
            "obstruction": obstruction,
        },
    )

    decision = check_degree_sequence(request)

    assert decision["accepted"] is True
    assert decision["conclusion"] == "FALSE"


def test_checker_rejects_fabricated_odd_sum_obstruction() -> None:
    """An ODD_SUM obstruction whose sum is even is fabricated."""
    obstruction = {
        "kind": "ODD_SUM",
        "degree_sum": 6,
    }
    request = _request(
        sequence=[3, 1, 1, 1],
        candidate={
            "result_schema_version": "1",
            "degree_sequence": [3, 1, 1, 1],
            "conclusion": "NON_GRAPHICAL",
            "graph_uri": None,
            "graph": None,
            "obstruction": obstruction,
        },
        certificate_payload={
            "method": "ODD_SUM_OBSTRUCTION",
            "degree_sequence": [3, 1, 1, 1],
            "conclusion": "NON_GRAPHICAL",
            "graph_uri": None,
            "obstruction": obstruction,
        },
    )

    decision = check_degree_sequence(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"
