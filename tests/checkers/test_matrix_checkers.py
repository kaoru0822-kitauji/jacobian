from __future__ import annotations

import pytest

from jacobian_checkers.matrices import (
    check_kernel_vector,
    check_maxdet_enumeration,
    check_maximizer_witness,
)


@pytest.mark.contract
def test_kernel_checker_accepts_exact_nonzero_vector() -> None:
    decision = check_kernel_vector(
        _witness_request(
            candidate={
                "rows": 2,
                "cols": 2,
                "entries": [["2", "4"], ["1", "2"]],
            },
            vector=[
                {"num": "-2", "den": "1"},
                {"num": "1", "den": "1"},
            ],
        )
    )

    assert decision["accepted"] is True
    assert decision["conclusion"] == "FALSE"


@pytest.mark.contract
def test_kernel_checker_rejects_zero_vector() -> None:
    decision = check_kernel_vector(
        _witness_request(
            candidate={
                "rows": 2,
                "cols": 2,
                "entries": [["2", "4"], ["1", "2"]],
            },
            vector=[
                {"num": "0", "den": "1"},
                {"num": "0", "den": "1"},
            ],
        )
    )

    assert decision["accepted"] is False


@pytest.mark.contract
def test_maxdet_checker_replays_all_512_matrices() -> None:
    bindings = {
        "claim_digest": "sha256:" + "a" * 64,
        "semantics_digest": "sha256:" + "b" * 64,
        "candidate_digest": "sha256:" + "c" * 64,
        "scope_digest": None,
        "encoding_digest": None,
    }
    decision = check_maxdet_enumeration(
        {
            "request_version": "1",
            "claim": {
                "payload": {
                    "predicate": "maximize_absolute_determinant",
                    "scope": {
                        "rows": 3,
                        "cols": 3,
                        "entries": [-1, 1],
                    },
                }
            },
            "candidate": {
                "payload": {
                    "rows": 3,
                    "cols": 3,
                    "entries": [
                        [-1, -1, -1],
                        [-1, -1, 1],
                        [-1, 1, -1],
                    ],
                }
            },
            "scope": None,
            "certificate": {
                "payload": {
                    "certificate_type": "matrix.maxdet_enumeration",
                    "format_version": "1",
                    "bindings": bindings,
                    "payload": {
                        "maximum": {"num": "4", "den": "1"},
                        "objects_checked": 512,
                    },
                }
            },
            "expected_bindings": bindings,
        }
    )

    assert decision["accepted"] is True
    assert decision["coverage"] == "EXHAUSTIVE"


@pytest.mark.contract
def test_maximizer_witness_checker_replays_scope() -> None:
    bindings = {
        "claim_digest": "sha256:" + "a" * 64,
        "semantics_digest": "sha256:" + "b" * 64,
        "candidate_digest": "sha256:" + "c" * 64,
        "scope_digest": None,
        "encoding_digest": None,
    }
    matrix = {
        "rows": 3,
        "cols": 3,
        "entries": [
            [-1, -1, -1],
            [-1, -1, 1],
            [-1, 1, -1],
        ],
    }
    decision = check_maximizer_witness(
        {
            "request_version": "1",
            "claim": {
                "payload": {
                    "predicate": "maximize_absolute_determinant",
                    "scope": {"rows": 3, "cols": 3, "entries": [-1, 1]},
                }
            },
            "candidate": {"payload": matrix},
            "witness": {
                "payload": {
                    "witness_format": "matrix.maximizer",
                    "format_version": "1",
                    "role": "SUPPORTS_CLAIM",
                    "bindings": bindings,
                    "payload": {
                        "matrix": matrix,
                        "objective_value": {"num": "4", "den": "1"},
                        "index": 0,
                    },
                }
            },
            "expected_bindings": bindings,
        }
    )

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"
    assert decision["coverage"] == "EXHAUSTIVE"


@pytest.mark.contract
def test_maximizer_witness_checker_rejects_different_bound_candidate() -> None:
    bindings = {
        "claim_digest": "sha256:" + "a" * 64,
        "semantics_digest": "sha256:" + "b" * 64,
        "candidate_digest": "sha256:" + "c" * 64,
        "scope_digest": None,
        "encoding_digest": None,
    }
    maximizer = {
        "rows": 3,
        "cols": 3,
        "entries": [
            [-1, -1, -1],
            [-1, -1, 1],
            [-1, 1, -1],
        ],
    }
    decision = check_maximizer_witness(
        {
            "request_version": "1",
            "claim": {
                "payload": {
                    "predicate": "maximize_absolute_determinant",
                    "scope": {"rows": 3, "cols": 3, "entries": [-1, 1]},
                }
            },
            "candidate": {
                "payload": {
                    "rows": 3,
                    "cols": 3,
                    "entries": [[1, 1, 1], [1, 1, 1], [1, 1, 1]],
                }
            },
            "witness": {
                "payload": {
                    "witness_format": "matrix.maximizer",
                    "format_version": "1",
                    "role": "SUPPORTS_CLAIM",
                    "bindings": bindings,
                    "payload": {
                        "matrix": maximizer,
                        "objective_value": {"num": "4", "den": "1"},
                        "index": 0,
                    },
                }
            },
            "expected_bindings": bindings,
        }
    )

    assert decision["accepted"] is False


def _witness_request(
    *,
    candidate: dict[str, object],
    vector: list[dict[str, str]],
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
        "claim": {"payload": {"predicate": "is_nonsingular"}},
        "candidate": {"payload": candidate},
        "witness": {
            "payload": {
                "witness_format": "matrix.kernel_vector",
                "format_version": "1",
                "role": "DEFEATS_CANDIDATE",
                "bindings": bindings,
                "payload": {"vector": vector},
            }
        },
        "expected_bindings": bindings,
    }
