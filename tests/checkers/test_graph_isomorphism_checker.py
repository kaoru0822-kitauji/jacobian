from __future__ import annotations

from copy import deepcopy
from typing import Any

from jacobian_checkers.graph_isomorphism import check_isomorphism


def _request() -> dict[str, Any]:
    bindings = {
        "claim_digest": "sha256:" + "a" * 64,
        "semantics_digest": "sha256:" + "b" * 64,
        "candidate_digest": "sha256:" + "c" * 64,
        "scope_digest": "sha256:" + "d" * 64,
        "encoding_digest": None,
    }
    pair_uri = "artifact://sha256/" + "1" * 64
    mapping_uri = "artifact://sha256/" + "2" * 64
    left_graph_uri = "artifact://sha256/" + "3" * 64
    right_graph_uri = "artifact://sha256/" + "4" * 64
    graph_schema_uri = "artifact://sha256/" + "5" * 64
    graph_semantics_uri = "artifact://sha256/" + "6" * 64
    left_graph_digest = "sha256:" + "1" * 64
    right_graph_digest = "sha256:" + "2" * 64
    left = {
        "graph_schema_version": "1",
        "vertices": ["a", "b", "c"],
        "edges": [["a", "b"], ["b", "c"]],
    }
    right = {
        "graph_schema_version": "1",
        "vertices": ["x", "y", "z"],
        "edges": [["x", "z"], ["y", "z"]],
    }
    return {
        "request_version": "1",
        "claim": {
            "payload": {
                "claim_schema_version": "1",
                "predicate": "MAPPING_IS_GRAPH_ISOMORPHISM",
                "graph_pair_uri": pair_uri,
                "mapping_uri": mapping_uri,
            }
        },
        "scope": {
            "artifact_uri": pair_uri,
            "payload": {
                "pair_schema_version": "1",
                "left_graph_uri": left_graph_uri,
                "right_graph_uri": right_graph_uri,
                "left_graph_digest": left_graph_digest,
                "right_graph_digest": right_graph_digest,
                "graph_schema_uri": graph_schema_uri,
                "graph_semantics_uri": graph_semantics_uri,
                "left": deepcopy(left),
                "right": deepcopy(right),
            },
        },
        "candidate": {
            "artifact_uri": mapping_uri,
            "payload": {
                "mapping_schema_version": "1",
                "mapping": {"a": "x", "b": "z", "c": "y"},
            },
        },
        "certificate": {
            "payload": {
                "evidence_schema_version": "1",
                "certificate_type": "graph.isomorphism_replay",
                "format_version": "1",
                "bindings": deepcopy(bindings),
                "payload_digest": "sha256:" + "e" * 64,
                "payload": {
                    "method": "DIRECT_ADJACENCY_REPLAY",
                    "graph_pair_uri": pair_uri,
                    "mapping_uri": mapping_uri,
                    "left_graph_uri": left_graph_uri,
                    "right_graph_uri": right_graph_uri,
                    "left_graph_digest": left_graph_digest,
                    "right_graph_digest": right_graph_digest,
                    "graph_schema_uri": graph_schema_uri,
                    "graph_semantics_uri": graph_semantics_uri,
                },
            }
        },
        "expected_bindings": deepcopy(bindings),
        "supporting_artifacts": [
            {
                "artifact_uri": left_graph_uri,
                "object_digest": left_graph_digest,
                "schema_uri": graph_schema_uri,
                "semantics_uri": graph_semantics_uri,
                "payload": deepcopy(left),
            },
            {
                "artifact_uri": right_graph_uri,
                "object_digest": right_graph_digest,
                "schema_uri": graph_schema_uri,
                "semantics_uri": graph_semantics_uri,
                "payload": deepcopy(right),
            },
        ],
    }


def test_checker_accepts_an_explicit_isomorphism() -> None:
    decision = check_isomorphism(_request())

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"
    assert decision["coverage"] == "EXHAUSTIVE"


def test_checker_certifies_that_a_bad_mapping_is_not_an_isomorphism() -> None:
    request = _request()
    request["candidate"]["payload"]["mapping"] = {
        "a": "x",
        "b": "y",
        "c": "z",
    }

    decision = check_isomorphism(request)

    assert decision["accepted"] is True
    assert decision["conclusion"] == "FALSE"


def test_checker_rejects_mapping_or_scope_substitution() -> None:
    request = _request()
    request["certificate"]["payload"]["payload"]["mapping_uri"] = (
        "artifact://sha256/" + "9" * 64
    )

    decision = check_isomorphism(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_checker_rejects_source_graph_substitution() -> None:
    request = _request()
    request["certificate"]["payload"]["payload"]["left_graph_uri"] = (
        "artifact://sha256/" + "9" * 64
    )

    decision = check_isomorphism(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_checker_rejects_embedded_graph_substitution() -> None:
    request = _request()
    request["scope"]["payload"]["left"]["edges"] = []

    decision = check_isomorphism(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_checker_rejects_malformed_graph_data() -> None:
    request = _request()
    request["scope"]["payload"]["left"]["edges"] = [["b", "a"]]

    decision = check_isomorphism(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"
