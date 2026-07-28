from __future__ import annotations

import pytest

from jacobian_checkers import matrices as matrix_checkers
from jacobian_checkers.matrices import (
    check_kernel_vector,
    check_maxdet_enumeration,
    check_maximizer_witness,
)


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


def test_maximizer_witness_checker_accepts_an_alternative_bound_maximizer() -> None:
    bindings = _bindings()
    proposed = {
        "rows": 3,
        "cols": 3,
        "entries": [[1, 1, 0], [1, 0, 1], [0, 1, 1]],
    }
    alternative = {
        "rows": 3,
        "cols": 3,
        "entries": [[1, 0, 1], [0, 1, 1], [1, 1, 0]],
    }

    decision = check_maximizer_witness(
        _maximizer_request(
            scope={"rows": 3, "cols": 3, "entries": [0, 1]},
            candidate=alternative,
            proposed=proposed,
            objective_value=2,
            bindings=bindings,
        )
    )

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"


def test_maximizer_witness_checker_rejects_nonmaximal_bound_candidate() -> None:
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


@pytest.mark.slow
def test_maximizer_witness_checker_replays_all_65536_matrices() -> None:
    matrix = {
        "rows": 4,
        "cols": 4,
        "entries": [
            [1, 1, 1, 1],
            [1, -1, 1, -1],
            [1, 1, -1, -1],
            [1, -1, -1, 1],
        ],
    }

    decision = check_maximizer_witness(
        _maximizer_request(
            scope={"rows": 4, "cols": 4, "entries": [-1, 1]},
            candidate=matrix,
            proposed=matrix,
            objective_value=16,
            bindings=_bindings(),
        )
    )

    assert decision["accepted"] is True
    assert decision["detail"] == "replayed all 65536 matrices in the declared scope"


def test_maximizer_witness_checker_rejects_over_budget_before_enumeration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_determinant(_: list[list[int]]) -> int:
        raise AssertionError("over-budget scope must not be enumerated")

    monkeypatch.setattr(matrix_checkers, "_determinant", unexpected_determinant)
    matrix = {
        "rows": 5,
        "cols": 5,
        "entries": [[1] * 5 for _ in range(5)],
    }

    decision = check_maximizer_witness(
        _maximizer_request(
            scope={"rows": 5, "cols": 5, "entries": [-1, 1]},
            candidate=matrix,
            proposed=matrix,
            objective_value=0,
            bindings=_bindings(),
        )
    )

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"
    assert decision["detail"] == "scope exceeds the independent checker limit"


def _bindings() -> dict[str, object]:
    return {
        "claim_digest": "sha256:" + "a" * 64,
        "semantics_digest": "sha256:" + "b" * 64,
        "candidate_digest": "sha256:" + "c" * 64,
        "scope_digest": None,
        "encoding_digest": None,
    }


def _maximizer_request(
    *,
    scope: dict[str, object],
    candidate: dict[str, object],
    proposed: dict[str, object],
    objective_value: int,
    bindings: dict[str, object],
) -> dict[str, object]:
    return {
        "request_version": "1",
        "claim": {
            "payload": {
                "predicate": "maximize_absolute_determinant",
                "scope": scope,
            }
        },
        "candidate": {"payload": candidate},
        "witness": {
            "payload": {
                "witness_format": "matrix.maximizer",
                "format_version": "1",
                "role": "SUPPORTS_CLAIM",
                "bindings": bindings,
                "payload": {
                    "matrix": proposed,
                    "objective_value": {"num": str(objective_value), "den": "1"},
                    "index": 0,
                },
            }
        },
        "expected_bindings": bindings,
    }


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
