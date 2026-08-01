"""Public-behavior tests for the directed graph/path search plugin."""

from __future__ import annotations

import pytest

from jacobian.plugins.graph_paths import (
    evaluate_capability,
    find_witness_capability,
    materialize,
    reductions_capability,
)


def _path_closure_candidate() -> dict:
    return {
        "vertices": ["s", "a", "b", "x", "t1", "t2"],
        "arcs": [
            ["s", "a"],
            ["a", "x"],
            ["s", "b"],
            ["b", "x"],
            ["x", "t1"],
            ["x", "t2"],
        ],
        "source": "s",
        "terminals": ["t1", "t2"],
        "intended_paths": [
            ["s", "a", "x", "t1"],
            ["s", "b", "x", "t2"],
        ],
    }


def _bipartite_candidate() -> dict:
    # Triangle plus three isolated vertices.
    return {
        "vertices": ["v0", "v1", "v2", "u0", "u1", "u2"],
        "arcs": [["v0", "v1"], ["v1", "v2"], ["v2", "v0"]],
    }


def test_evaluate_path_closure_is_incomplete() -> None:
    claim = {"predicate": "intended_paths_complete", "simple": True}
    response = evaluate_capability(
        {"claim": claim, "candidate": _path_closure_candidate()}
    )
    assert response["conclusion"] == "FALSE"
    assert response["failure_classifications"] == ["omitted_semantic_object"]
    assert response["features"] == {"num_actual": "4", "num_intended": "2"}


def test_path_closure_rejects_candidate_without_semantic_roles() -> None:
    claim = {"predicate": "intended_paths_complete", "simple": True}
    candidate = {"vertices": ["s", "t"], "arcs": [["s", "t"]]}

    with pytest.raises(ValueError, match="graph evaluation request does not match"):
        evaluate_capability({"claim": claim, "candidate": candidate})


def test_bounded_path_search_does_not_claim_exhaustive_coverage() -> None:
    claim = {
        "predicate": "intended_paths_complete",
        "simple": True,
        "max_path_length": 2,
    }
    candidate = {
        "vertices": ["s", "a", "t"],
        "arcs": [["s", "a"], ["a", "t"]],
        "source": "s",
        "terminals": ["t"],
        "intended_paths": [],
    }

    resp = find_witness_capability(
        {
            "claim": claim,
            "candidate": candidate,
            "witness_role": "DEFEATS_CANDIDATE",
        }
    )

    assert resp["status"] == "SEARCH_EXHAUSTED"
    assert resp["coverage"] == "BOUNDED"


def test_negative_support_search_keeps_assurance_metadata() -> None:
    claim = {"predicate": "is_bipartite"}
    resp = find_witness_capability(
        {
            "claim": claim,
            "candidate": _bipartite_candidate(),
            "witness_role": "SUPPORTS_CLAIM",
        }
    )

    assert resp["status"] == "SEARCH_EXHAUSTED"
    assert resp["coverage"] == "EXHAUSTIVE"
    assert resp["arithmetic"] == "EXACT_INTEGER"


def test_path_claim_rejects_source_as_terminal() -> None:
    claim = {"predicate": "intended_paths_complete", "simple": True}
    candidate = {
        "vertices": ["s", "t"],
        "arcs": [["s", "t"]],
        "source": "s",
        "terminals": ["s", "t"],
        "intended_paths": [["s", "t"]],
    }

    with pytest.raises(ValueError, match="graph capability request does not match"):
        find_witness_capability(
            {
                "claim": claim,
                "candidate": candidate,
                "witness_role": "DEFEATS_CANDIDATE",
            }
        )


def test_evaluate_bipartite_true() -> None:
    cand = {
        "vertices": ["a", "b", "c"],
        "arcs": [["a", "b"], ["b", "c"]],
    }
    claim = {"predicate": "is_bipartite"}
    resp = evaluate_capability({"claim": claim, "candidate": cand})
    assert resp["conclusion"] == "TRUE"


def test_evaluate_bipartite_false_for_triangle() -> None:
    claim = {"predicate": "is_bipartite"}
    resp = evaluate_capability({"claim": claim, "candidate": _bipartite_candidate()})
    assert resp["conclusion"] == "FALSE"
    assert resp["objectives"] == {"is_bipartite": False}


def test_find_witness_returns_omitted_path() -> None:
    claim = {"predicate": "intended_paths_complete", "simple": True}
    resp = find_witness_capability(
        {
            "claim": claim,
            "candidate": _path_closure_candidate(),
            "witness_role": "DEFEATS_CANDIDATE",
        }
    )
    assert resp["status"] == "FOUND"
    assert resp["witness_format"] == "graph.omitted_path"
    path = resp["witness"]["path"]
    assert path in (
        ["s", "a", "x", "t2"],
        ["s", "b", "x", "t1"],
    )


def test_find_witness_returns_odd_cycle() -> None:
    claim = {"predicate": "is_bipartite"}
    resp = find_witness_capability(
        {
            "claim": claim,
            "candidate": _bipartite_candidate(),
            "witness_role": "DEFEATS_CANDIDATE",
        }
    )
    assert resp["status"] == "FOUND"
    assert resp["witness_format"] == "graph.odd_cycle"
    assert len(resp["witness"]["cycle"]) == 3


def test_materialize_enumerates_all_four_paths() -> None:
    claim = {"predicate": "intended_paths_complete", "simple": True}
    resp = materialize({"claim": claim, "candidate": _path_closure_candidate()})
    family = {tuple(p) for p in resp["family"]}
    assert family == {
        ("s", "a", "x", "t1"),
        ("s", "a", "x", "t2"),
        ("s", "b", "x", "t1"),
        ("s", "b", "x", "t2"),
    }


def test_reduction_capability_for_path_closure() -> None:
    claim = {"predicate": "intended_paths_complete", "simple": True}
    response = reductions_capability(
        {
            "target_kind": "candidate",
            "target": _path_closure_candidate(),
            "claim": claim,
        }
    )
    assert response["current_objectives"] == {}
    # Deleting vertices b and t1 (outside the chosen omitted path) must be proposed.
    vertices_to_delete = {
        next(
            iter(
                set(_path_closure_candidate()["vertices"])
                - set(item["payload"]["vertices"])
            )
        )
        for item in response["reductions"]
        if item["reducer"] == "delete_vertex"
    }
    assert {"b", "t1"}.issubset(vertices_to_delete) or {"b", "t2"}.issubset(
        vertices_to_delete
    )


def test_reduction_capability_projects_requested_objectives() -> None:
    response = reductions_capability(
        {
            "target_kind": "candidate",
            "target": _path_closure_candidate(),
            "claim": {"predicate": "intended_paths_complete", "simple": True},
            "reducers": ["delete_vertex"],
            "objectives": ["vertices"],
        }
    )

    assert set(response["current_objectives"]) == {"vertices"}
    assert all(
        set(item["objectives"]) == {"vertices"} for item in response["reductions"]
    )


def test_reductions_for_bipartite_triangle() -> None:
    claim = {"predicate": "is_bipartite"}
    response = reductions_capability(
        {"target_kind": "candidate", "target": _bipartite_candidate(), "claim": claim}
    )
    vertices_to_delete = {
        next(
            iter(
                set(_bipartite_candidate()["vertices"])
                - set(item["payload"]["vertices"])
            )
        )
        for item in response["reductions"]
        if item["reducer"] == "delete_vertex"
    }
    assert {"u0", "u1", "u2"}.issubset(vertices_to_delete)
    # No triangle edge or vertex should be proposed for deletion.
    for item in response["reductions"]:
        if item["reducer"] == "delete_vertex":
            deleted = set(_bipartite_candidate()["vertices"]) - set(
                item["payload"]["vertices"]
            )
            assert deleted <= {"u0", "u1", "u2"}
    assert all(item["reducer"] != "delete_edge" for item in response["reductions"])


def test_evaluation_does_not_grant_verification_authority() -> None:
    response = evaluate_capability(
        {"claim": {"predicate": "is_bipartite"}, "candidate": _bipartite_candidate()}
    )
    assert "verified" not in response
