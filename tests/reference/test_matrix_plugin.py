"""Public-behavior tests for the integer-matrix search plugin."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import pytest

from jacobian.plugins import matrices as matrix_plugin
from jacobian.plugins.matrices import (
    evaluate,
    find_witness,
    materialize,
    reductions,
    validate_candidate,
    validate_claim,
)


def _kernel_candidate() -> dict:
    return {
        "rows": 2,
        "cols": 2,
        "entries": [["2", "4"], ["1", "2"]],
    }


def _maxdet_scope() -> dict:
    return {
        "rows": 3,
        "cols": 3,
        "entries": [-1, 1],
    }


def _maxdet_maximizer() -> dict:
    return {
        "rows": 3,
        "cols": 3,
        "entries": [
            [-1, -1, -1],
            [-1, -1, 1],
            [-1, 1, -1],
        ],
    }


def test_validate_candidate_accepts_kernel_fixture() -> None:
    assert validate_candidate(_kernel_candidate()) == []


def test_validate_candidate_rejects_floats() -> None:
    cand = _kernel_candidate()
    cand["entries"] = [[2.0, 4], [1, 2]]
    assert validate_candidate(cand)


def test_validate_candidate_rejects_bools() -> None:
    cand = _kernel_candidate()
    cand["entries"] = [[True, 4], [1, 2]]
    assert validate_candidate(cand)


def test_validate_candidate_rejects_non_rectangular() -> None:
    cand = _kernel_candidate()
    cand["entries"] = [[2, 4, 0], [1, 2]]
    assert validate_candidate(cand)


def test_determinant_predicate_rejects_rectangular_matrix() -> None:
    candidate = {
        "rows": 2,
        "cols": 3,
        "entries": [[1, 0, 0], [0, 1, 0]],
    }

    resp = evaluate({"claim": {"predicate": "is_nonsingular"}, "candidate": candidate})

    assert resp["input"]["status"] == "REJECTED"


def test_maxdet_rejects_rectangular_scope() -> None:
    claim = {
        "predicate": "maximize_absolute_determinant",
        "scope": {"rows": 2, "cols": 3, "entries": [-1, 1]},
    }

    assert validate_claim(claim)


def test_validate_claim_accepts_supported_predicates() -> None:
    assert validate_claim({"predicate": "is_nonsingular"}) == []
    assert (
        validate_claim(
            {"predicate": "maximize_absolute_determinant", "scope": _maxdet_scope()}
        )
        == []
    )


def test_validate_claim_rejects_missing_scope() -> None:
    errors = validate_claim({"predicate": "maximize_absolute_determinant"})
    assert errors


def test_evaluate_kernel_matrix_is_singular() -> None:
    claim = {"predicate": "is_nonsingular"}
    resp = evaluate({"claim": claim, "candidate": _kernel_candidate()})
    assert resp["input"]["status"] == "ACCEPTED"
    result = resp["results"][0]
    assert result["is_singular"] is True
    assert result["objective"]["value"] == {"num": "0", "den": "1"}
    vec = result["proposed_witness"]["payload"]["vector"]
    assert _matrix_times_vector(_kernel_candidate()["entries"], vec) == [
        Fraction(0),
        Fraction(0),
    ]


def test_find_witness_kernel_vector() -> None:
    claim = {"predicate": "is_nonsingular"}
    resp = find_witness(
        {
            "claim": claim,
            "candidate": _kernel_candidate(),
            "witness_role": "DEFEATS_CANDIDATE",
        }
    )
    assert resp["status"] == "FOUND"
    assert resp["witness_format"] == "matrix.kernel_vector"
    vec = resp["witness"]["vector"]
    assert _matrix_times_vector(_kernel_candidate()["entries"], vec) == [
        Fraction(0),
        Fraction(0),
    ]
    assert any(v != {"num": "0", "den": "1"} for v in vec)


def test_find_witness_rejects_unsupported_role() -> None:
    resp = find_witness(
        {
            "claim": {"predicate": "is_nonsingular"},
            "candidate": _kernel_candidate(),
            "witness_role": "SUPPORTS_CLAIM",
        }
    )

    assert resp["input"]["status"] == "REJECTED"


def test_evaluate_maxdet_maximizer() -> None:
    claim = {"predicate": "maximize_absolute_determinant", "scope": _maxdet_scope()}
    resp = evaluate({"claim": claim, "candidate": _maxdet_maximizer()})
    result = resp["results"][0]
    assert result["objective"]["value"] == {"num": "4", "den": "1"}


def test_evaluate_maxdet_rejects_candidate_outside_scope() -> None:
    claim = {"predicate": "maximize_absolute_determinant", "scope": _maxdet_scope()}
    candidate = _maxdet_maximizer()
    candidate["entries"][0][0] = 100

    resp = evaluate({"claim": claim, "candidate": candidate})

    assert resp["input"]["status"] == "REJECTED"
    assert "outside claim scope" in resp["input"]["errors"][0]


def test_find_witness_maxdet_returns_maximizer() -> None:
    claim = {"predicate": "maximize_absolute_determinant", "scope": _maxdet_scope()}
    resp = find_witness({"claim": claim, "witness_role": "SUPPORTS_CLAIM"})
    assert resp["status"] == "FOUND"
    assert resp["witness_format"] == "matrix.maximizer"
    mat = resp["witness"]["matrix"]
    assert all(entry in (-1, 1) for row in mat["entries"] for entry in row)
    det = _det_3x3(mat["entries"])
    assert abs(det) == 4


def test_find_witness_maxdet_requires_supporting_role() -> None:
    claim = {"predicate": "maximize_absolute_determinant", "scope": _maxdet_scope()}

    resp = find_witness(
        {
            "claim": claim,
            "witness_role": "DEFEATS_CANDIDATE",
        }
    )

    assert resp["input"]["status"] == "REJECTED"


def test_find_witness_maxdet_rejects_over_budget_before_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_iterator(_: dict[str, object]) -> object:
        raise AssertionError("over-budget scope must not be enumerated")

    monkeypatch.setattr(matrix_plugin, "_scope_iterator", unexpected_iterator)
    claim = {
        "predicate": "maximize_absolute_determinant",
        "scope": {"rows": 5, "cols": 5, "entries": [-1, 1]},
    }

    response = find_witness({"claim": claim, "witness_role": "SUPPORTS_CLAIM"})

    assert response["input"]["status"] == "REJECTED"
    assert response["input"]["errors"] == [
        "scope exceeds witness search limit of 65536 candidates"
    ]


def test_materialize_maxdet_scope_count() -> None:
    claim = {"predicate": "maximize_absolute_determinant", "scope": _maxdet_scope()}
    resp = materialize({"claim": claim})
    assert len(resp["family"]) == 512
    # The scenario maximizer must be present.
    entries = [m["candidate"]["entries"] for m in resp["family"]]
    assert _maxdet_maximizer()["entries"] in entries


def test_reductions_kernel_fixture_is_minimal() -> None:
    claim = {"predicate": "is_nonsingular"}
    resp = reductions(
        {"target_kind": "candidate", "target": _kernel_candidate(), "claim": claim}
    )
    assert resp["input"]["status"] == "ACCEPTED"
    assert resp["reductions"] == []


def test_reductions_finds_singular_principal_submatrix() -> None:
    # 3x3 singular matrix with a singular 2x2 principal submatrix.
    cand = {
        "rows": 3,
        "cols": 3,
        "entries": [
            [1, 1, 0],
            [1, 1, 0],
            [0, 0, 1],
        ],
    }
    claim = {"predicate": "is_nonsingular"}
    resp = reductions({"target_kind": "candidate", "target": cand, "claim": claim})
    kinds = {r["reduction_kind"] for r in resp["reductions"]}
    assert "delete_row_column" in kinds


def test_results_are_unverified() -> None:
    resp = evaluate(
        {"claim": {"predicate": "is_nonsingular"}, "candidate": _kernel_candidate()}
    )
    assert resp["verified"] is False


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _matrix_times_vector(
    entries: list[list[Any]], vector: list[dict[str, str]]
) -> list[Fraction]:
    mat = [[Fraction(int(x)) for x in row] for row in entries]
    vec = [Fraction(int(v["num"]), int(v["den"])) for v in vector]
    result: list[Fraction] = []
    for row in mat:
        total = Fraction(0)
        for a, b in zip(row, vec, strict=True):
            total += a * b
        result.append(total)
    return result


def _det_3x3(m: list[list[int]]) -> int:
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
