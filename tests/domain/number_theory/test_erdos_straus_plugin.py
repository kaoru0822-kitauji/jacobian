"""Public-behavior tests for bounded Erdős-Straus search."""

from __future__ import annotations

import pytest

from jacobian.plugins.erdos_straus import (
    evaluate_capability,
    find_witness_capability,
)


def _claim(lower: int = 2, upper: int = 100) -> dict[str, object]:
    return {
        "predicate": "erdos_straus_range",
        "lower_bound": lower,
        "upper_bound": upper,
    }


def _candidate(lower: int = 2, upper: int = 100) -> dict[str, int]:
    return {"lower_bound": lower, "upper_bound": upper}


@pytest.mark.parametrize(
    ("claim", "candidate"),
    (
        (_claim(1, 100), _candidate()),
        (_claim(), _candidate(10, 9)),
        (_claim(), _candidate(2, 10_001)),
    ),
)
def test_capability_rejects_invalid_ranges(
    claim: dict[str, object], candidate: dict[str, int]
) -> None:
    with pytest.raises(ValueError):
        evaluate_capability({"claim": claim, "candidate": candidate})


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


@pytest.mark.parametrize(
    ("witness_request", "message"),
    (
        (
            {
                "claim": _claim(),
                "candidate": _candidate(),
                "witness_role": "DEFEATS_CANDIDATE",
            },
            "supports only SUPPORTS_CLAIM witnesses",
        ),
        (
            {
                "claim": _claim(2, 100),
                "candidate": _candidate(2, 99),
                "witness_role": "SUPPORTS_CLAIM",
            },
            "Erdős-Straus request does not match its contract",
        ),
    ),
)
def test_find_witness_rejects_wrong_role_or_range(
    witness_request: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        find_witness_capability(witness_request)
