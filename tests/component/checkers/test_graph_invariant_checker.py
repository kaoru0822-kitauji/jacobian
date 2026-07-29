from __future__ import annotations

from copy import deepcopy
from typing import Any

from jacobian_checkers.graph_invariants import (
    check_neighborhood_independence,
)


def _request() -> dict[str, Any]:
    bindings = {
        "claim_digest": "sha256:" + "a" * 64,
        "semantics_digest": "sha256:" + "b" * 64,
        "candidate_digest": "sha256:" + "c" * 64,
        "scope_digest": "sha256:" + "d" * 64,
        "encoding_digest": None,
    }
    graph_uri = "artifact://sha256/" + "1" * 64
    invariant_uri = "artifact://sha256/" + "2" * 64
    return {
        "request_version": "1",
        "claim": {
            "payload": {
                "claim_schema_version": "1",
                "predicate": "EXACT_NEIGHBORHOOD_INDEPENDENCE_PROFILE",
                "source_graph_uri": graph_uri,
            }
        },
        "scope": {
            "artifact_uri": graph_uri,
            "payload": {
                "graph_schema_version": "1",
                "vertices": ["a", "b", "c"],
                "edges": [["a", "b"], ["b", "c"]],
            },
        },
        "candidate": {
            "artifact_uri": invariant_uri,
            "payload": {
                "invariant_schema_version": "1",
                "graph_uri": graph_uri,
                "records": [
                    {
                        "vertex": "a",
                        "neighborhood": ["b"],
                        "independent_set": ["b"],
                        "independence_number": 1,
                    },
                    {
                        "vertex": "b",
                        "neighborhood": ["a", "c"],
                        "independent_set": ["a", "c"],
                        "independence_number": 2,
                    },
                    {
                        "vertex": "c",
                        "neighborhood": ["b"],
                        "independent_set": ["b"],
                        "independence_number": 1,
                    },
                ],
                "total": 4,
                "average": {"num": "4", "den": "3"},
                "maximum_neighborhood_order": 24,
                "backend": "networkx",
                "backend_version": "3.6.1",
            },
        },
        "certificate": {
            "payload": {
                "evidence_schema_version": "1",
                "certificate_type": "graph.neighborhood_independence",
                "format_version": "1",
                "bindings": deepcopy(bindings),
                "payload_digest": "sha256:" + "e" * 64,
                "payload": {
                    "method": "EXACT_STDLIB_BRANCH_AND_BOUND",
                    "source_graph_uri": graph_uri,
                    "invariant_uri": invariant_uri,
                },
            }
        },
        "expected_bindings": deepcopy(bindings),
    }


def test_checker_replays_every_neighborhood_optimum() -> None:
    decision = check_neighborhood_independence(_request())

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"
    assert decision["method"] == "CHECKED_CERTIFICATE"


def test_checker_rejects_a_nonmaximal_local_witness() -> None:
    request = _request()
    middle = request["candidate"]["payload"]["records"][1]
    middle["independent_set"] = ["a"]
    middle["independence_number"] = 1
    request["candidate"]["payload"]["total"] = 3
    request["candidate"]["payload"]["average"] = {"num": "1", "den": "1"}

    decision = check_neighborhood_independence(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"
