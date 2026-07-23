"""Public-behavior tests for the directed graph/path search plugin."""

from __future__ import annotations

from jacobian.plugins.graph_paths import (
    evaluate,
    find_witness,
    materialize,
    reductions,
    reductions_capability,
    validate_candidate,
    validate_claim,
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


def test_validate_candidate_accepts_path_closure_fixture() -> None:
    assert validate_candidate(_path_closure_candidate()) == []


def test_validate_candidate_rejects_duplicate_vertices() -> None:
    cand = _path_closure_candidate()
    cand["vertices"] = ["s", "a", "a", "x", "t1", "t2"]
    assert any("unique" in e for e in validate_candidate(cand))


def test_validate_candidate_rejects_out_of_domain_arc() -> None:
    cand = _path_closure_candidate()
    cand["arcs"].append(["s", "z"])
    assert any("out of domain" in e for e in validate_candidate(cand))


def test_validate_claim_accepts_supported_predicates() -> None:
    assert (
        validate_claim({"predicate": "intended_paths_complete", "simple": True}) == []
    )
    assert validate_claim({"predicate": "is_bipartite"}) == []


def test_validate_claim_rejects_unknown_predicate() -> None:
    errors = validate_claim({"predicate": "has_hamiltonian_path"})
    assert errors


def test_evaluate_path_closure_is_incomplete() -> None:
    claim = {"predicate": "intended_paths_complete", "simple": True}
    resp = evaluate({"claim": claim, "candidate": _path_closure_candidate()})
    assert resp["input"]["status"] == "ACCEPTED"
    result = resp["results"][0]
    assert result["objective"]["value"] is False
    assert result["objective"]["num_actual"] == 4
    assert result["objective"]["num_intended"] == 2
    assert result["proposed_witness"]["payload"]["path"] not in [
        ["s", "a", "x", "t1"],
        ["s", "b", "x", "t2"],
    ]


def test_path_closure_rejects_candidate_without_semantic_roles() -> None:
    claim = {"predicate": "intended_paths_complete", "simple": True}
    candidate = {"vertices": ["s", "t"], "arcs": [["s", "t"]]}

    resp = evaluate({"claim": claim, "candidate": candidate})

    assert resp["input"]["status"] == "REJECTED"


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

    resp = find_witness(
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
    resp = find_witness(
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

    resp = find_witness(
        {
            "claim": claim,
            "candidate": candidate,
            "witness_role": "DEFEATS_CANDIDATE",
        }
    )

    assert resp["input"]["status"] == "REJECTED"


def test_evaluate_bipartite_true() -> None:
    cand = {
        "vertices": ["a", "b", "c"],
        "arcs": [["a", "b"], ["b", "c"]],
    }
    claim = {"predicate": "is_bipartite"}
    resp = evaluate({"claim": claim, "candidate": cand})
    assert resp["results"][0]["objective"]["value"] is True
    assert resp["results"][0]["proposed_witness"]["witness_format"] == "graph.2coloring"


def test_evaluate_bipartite_false_for_triangle() -> None:
    claim = {"predicate": "is_bipartite"}
    resp = evaluate({"claim": claim, "candidate": _bipartite_candidate()})
    result = resp["results"][0]
    assert result["objective"]["value"] is False
    assert result["proposed_witness"]["witness_format"] == "graph.odd_cycle"
    cycle = result["proposed_witness"]["payload"]["cycle"]
    assert len(cycle) == 3


def test_find_witness_returns_omitted_path() -> None:
    claim = {"predicate": "intended_paths_complete", "simple": True}
    resp = find_witness(
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
    resp = find_witness(
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


def test_reductions_for_path_closure() -> None:
    claim = {"predicate": "intended_paths_complete", "simple": True}
    resp = reductions(
        {
            "target_kind": "candidate",
            "target": _path_closure_candidate(),
            "claim": claim,
        }
    )
    assert resp["input"]["status"] == "ACCEPTED"
    kinds = {r["reduction_kind"] for r in resp["reductions"]}
    assert "delete_vertex" in kinds
    # Deleting vertices b and t1 (outside the chosen omitted path) must be proposed.
    vertices_to_delete = {
        r["vertex"]
        for r in resp["reductions"]
        if r["reduction_kind"] == "delete_vertex"
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
    resp = reductions(
        {"target_kind": "candidate", "target": _bipartite_candidate(), "claim": claim}
    )
    assert resp["input"]["status"] == "ACCEPTED"
    vertices_to_delete = {
        r["vertex"]
        for r in resp["reductions"]
        if r["reduction_kind"] == "delete_vertex"
    }
    assert {"u0", "u1", "u2"}.issubset(vertices_to_delete)
    # No triangle edge or vertex should be proposed for deletion.
    for r in resp["reductions"]:
        if r["reduction_kind"] == "delete_vertex":
            assert r["vertex"] in {"u0", "u1", "u2"}
        if r["reduction_kind"] == "delete_edge":
            assert tuple(r["edge"]) not in {("v0", "v1"), ("v1", "v2"), ("v2", "v0")}


def test_results_are_unverified() -> None:
    resp = evaluate(
        {"claim": {"predicate": "is_bipartite"}, "candidate": _bipartite_candidate()}
    )
    assert resp["verified"] is False
