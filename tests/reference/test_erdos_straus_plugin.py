"""Public-behavior tests for bounded Erdős-Straus search."""

from __future__ import annotations

from jacobian.plugins.erdos_straus import (
    evaluate_capability,
    find_witness_capability,
    validate_candidate,
    validate_claim,
)


def _claim(lower: int = 2, upper: int = 100) -> dict[str, object]:
    return {
        "predicate": "erdos_straus_range",
        "lower_bound": lower,
        "upper_bound": upper,
    }


def _candidate(lower: int = 2, upper: int = 100) -> dict[str, int]:
    return {"lower_bound": lower, "upper_bound": upper}


def test_validate_bounded_range() -> None:
    assert validate_claim(_claim()) == []
    assert validate_candidate(_candidate()) == []
    assert validate_claim(_claim(1, 100))
    assert validate_candidate(_candidate(10, 9))
    assert validate_candidate(_candidate(2, 10_001))


def test_evaluate_finds_every_decomposition_through_1000() -> None:
    response = evaluate_capability(
        {
            "claim": _claim(2, 1000),
            "candidate": _candidate(2, 1000),
        }
    )

    assert response["conclusion"] == "TRUE"
    assert response["coverage"] == "EXHAUSTIVE"
    assert response["objectives"] == {
        "range_size": 999,
        "decompositions_found": 999,
    }


def test_find_witness_returns_complete_exact_table() -> None:
    response = find_witness_capability(
        {
            "claim": _claim(2, 100),
            "candidate": _candidate(2, 100),
            "witness_role": "SUPPORTS_CLAIM",
        }
    )

    assert response["status"] == "FOUND"
    assert response["witness_format"] == "erdos_straus.decomposition_table"
    table = response["witness"]["decompositions"]
    assert [row["n"] for row in table] == list(range(2, 101))
    assert all(
        4 * row["x"] * row["y"] * row["z"]
        == row["n"] * (row["x"] * row["y"] + row["x"] * row["z"] + row["y"] * row["z"])
        for row in table
    )


def test_find_witness_rejects_wrong_role_or_range() -> None:
    for request in (
        {
            "claim": _claim(),
            "candidate": _candidate(),
            "witness_role": "DEFEATS_CANDIDATE",
        },
        {
            "claim": _claim(2, 100),
            "candidate": _candidate(2, 99),
            "witness_role": "SUPPORTS_CLAIM",
        },
    ):
        try:
            find_witness_capability(request)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid witness request was accepted")
