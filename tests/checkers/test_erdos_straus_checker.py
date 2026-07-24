from __future__ import annotations

import pytest

from jacobian_checkers.erdos_straus import check_decomposition_table


def _request(
    table: list[dict[str, int]],
    *,
    lower: int = 2,
    upper: int = 4,
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
        "claim": {
            "payload": {
                "predicate": {
                    "name": "erdos_straus_range",
                    "parameters": {
                        "lower_bound": lower,
                        "upper_bound": upper,
                    },
                }
            }
        },
        "candidate": {
            "payload": {
                "lower_bound": lower,
                "upper_bound": upper,
            }
        },
        "witness": {
            "payload": {
                "witness_format": "erdos_straus.decomposition_table",
                "format_version": "1",
                "role": "SUPPORTS_CLAIM",
                "bindings": bindings,
                "payload": {"decompositions": table},
            }
        },
        "expected_bindings": bindings,
    }


@pytest.mark.contract
def test_checker_accepts_complete_exact_table() -> None:
    decision = check_decomposition_table(
        _request(
            [
                {"n": 2, "x": 1, "y": 2, "z": 2},
                {"n": 3, "x": 1, "y": 4, "z": 12},
                {"n": 4, "x": 2, "y": 3, "z": 6},
            ]
        )
    )

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"
    assert decision["coverage"] == "EXHAUSTIVE"


@pytest.mark.contract
@pytest.mark.parametrize(
    "table",
    [
        [
            {"n": 2, "x": 1, "y": 2, "z": 2},
            {"n": 3, "x": 1, "y": 4, "z": 12},
        ],
        [
            {"n": 2, "x": 1, "y": 2, "z": 2},
            {"n": 3, "x": 1, "y": 4, "z": 11},
            {"n": 4, "x": 2, "y": 3, "z": 6},
        ],
        [
            {"n": 2, "x": 1, "y": 2, "z": 2},
            {"n": 3, "x": 1, "y": 4, "z": 12},
            {"n": 3, "x": 1, "y": 4, "z": 12},
            {"n": 4, "x": 2, "y": 3, "z": 6},
        ],
    ],
)
def test_checker_rejects_incomplete_invalid_or_duplicate_table(
    table: list[dict[str, int]],
) -> None:
    decision = check_decomposition_table(_request(table))

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


@pytest.mark.contract
def test_checker_rejects_range_substitution() -> None:
    request = _request(
        [
            {"n": 2, "x": 1, "y": 2, "z": 2},
            {"n": 3, "x": 1, "y": 4, "z": 12},
            {"n": 4, "x": 2, "y": 3, "z": 6},
        ]
    )
    request["candidate"]["payload"]["upper_bound"] = 5

    assert check_decomposition_table(request)["accepted"] is False
