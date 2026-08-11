from __future__ import annotations

from tests.component.checkers.exact_domain_checker_support import _request

from jacobian_checkers.finite_field_rank import (
    check_finite_field_linear_map_rank,
)


def _rank_request(
    *, rank: int = 1, candidate_entries: list[list[int]] | None = None
) -> dict[str, object]:
    presentation = {
        "characteristic": 2,
        "modulus_coefficients": [1, 1, 1],
        "generator": "a",
        "element_encoding_version": "power-basis-v1",
    }
    direction = {
        "presentation": presentation,
        "axis": {"name": "b", "labels": ["b1"]},
        "coordinates": [
            {"presentation": presentation, "coordinates": [1, 0]},
        ],
    }
    linear_map: dict[str, object] = {
        "source_axis": {"name": "source", "labels": ["B1"]},
        "target_axis": {"name": "target", "labels": ["y1", "y2"]},
        "matrix": {"prime": 2, "entries": [[1], [0]], "columns": 1},
    }
    matrix = linear_map["matrix"]
    assert isinstance(matrix, dict)
    candidate_map = dict(linear_map)
    candidate_map["matrix"] = {
        **matrix,
        "entries": candidate_entries or [[1], [0]],
    }
    return _request(
        "finite_field.linear_map.rank.compute",
        "finite-field.linear-map-rank.sympy-replay",
        {"direction": direction, "linear_map": linear_map},
        {"direction": direction, "linear_map": candidate_map, "rank": rank},
    )


def test_sympy_checker_accepts_exact_prime_field_rank() -> None:
    decision = check_finite_field_linear_map_rank(_rank_request())

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"


def test_sympy_checker_rejects_wrong_rank() -> None:
    decision = check_finite_field_linear_map_rank(_rank_request(rank=0))

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_sympy_checker_rejects_a_candidate_bound_to_another_map() -> None:
    decision = check_finite_field_linear_map_rank(
        _rank_request(candidate_entries=[[0], [0]])
    )

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"
