from __future__ import annotations

import pytest

from jacobian_checkers.graph_paths import (
    check_odd_cycle,
    check_path_enumeration,
    check_two_coloring,
)


@pytest.mark.contract
def test_odd_cycle_checker_rejects_even_cycle() -> None:
    decision = check_odd_cycle(
        _graph_witness_request(
            vertices=["a", "b", "c", "d"],
            arcs=[["a", "b"], ["b", "c"], ["c", "d"], ["d", "a"]],
            witness_format="graph.odd_cycle",
            role="DEFEATS_CANDIDATE",
            payload={"cycle": ["a", "b", "c", "d"]},
        )
    )

    assert decision["accepted"] is False


@pytest.mark.contract
def test_two_coloring_checker_requires_every_vertex() -> None:
    decision = check_two_coloring(
        _graph_witness_request(
            vertices=["a", "b", "isolated"],
            arcs=[["a", "b"]],
            witness_format="graph.2coloring",
            role="SUPPORTS_CLAIM",
            payload={"coloring": {"a": 0, "b": 1}},
        )
    )

    assert decision["accepted"] is False


@pytest.mark.contract
def test_two_coloring_checker_rejects_boolean_colors() -> None:
    decision = check_two_coloring(
        _graph_witness_request(
            vertices=["a", "b"],
            arcs=[["a", "b"]],
            witness_format="graph.2coloring",
            role="SUPPORTS_CLAIM",
            payload={"coloring": {"a": False, "b": True}},
        )
    )

    assert decision["accepted"] is False


@pytest.mark.contract
def test_path_enumeration_continues_through_intermediate_terminal() -> None:
    bindings = {
        "claim_digest": "sha256:" + "a" * 64,
        "semantics_digest": "sha256:" + "b" * 64,
        "candidate_digest": "sha256:" + "c" * 64,
        "scope_digest": "sha256:" + "d" * 64,
        "encoding_digest": None,
    }
    decision = check_path_enumeration(
        {
            "request_version": "1",
            "claim": {
                "payload": {
                    "predicate": "intended_paths_complete",
                    "simple": True,
                }
            },
            "candidate": {
                "payload": {
                    "vertices": ["s", "t1", "t2"],
                    "arcs": [["s", "t1"], ["t1", "t2"]],
                    "source": "s",
                    "terminals": ["t1", "t2"],
                    "intended_paths": [["s", "t1"], ["s", "t1", "t2"]],
                }
            },
            "scope": {"payload": {"simple": True, "max_length": 3}},
            "certificate": {
                "payload": {
                    "certificate_type": "graph.path_enumeration",
                    "format_version": "1",
                    "bindings": bindings,
                    "payload": {"actual_paths": [["s", "t1"], ["s", "t1", "t2"]]},
                }
            },
            "expected_bindings": bindings,
        }
    )

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"


def _graph_witness_request(
    *,
    vertices: list[str],
    arcs: list[list[str]],
    witness_format: str,
    role: str,
    payload: dict[str, object],
) -> dict[str, object]:
    bindings = {
        "claim_digest": "sha256:" + "a" * 64,
        "semantics_digest": "sha256:" + "b" * 64,
        "candidate_digest": "sha256:" + "c" * 64,
        "scope_digest": None,
        "encoding_digest": None,
    }
    return {
        "request_version": "1",
        "claim": {"payload": {"predicate": "is_bipartite"}},
        "candidate": {"payload": {"vertices": vertices, "arcs": arcs}},
        "witness": {
            "payload": {
                "witness_format": witness_format,
                "format_version": "1",
                "role": role,
                "bindings": bindings,
                "payload": payload,
            }
        },
        "expected_bindings": bindings,
    }
