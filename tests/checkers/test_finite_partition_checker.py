from __future__ import annotations

from typing import Any

from jacobian_checkers.finite_partition import check_partition


def _request(*, cases: list[dict[str, object]]) -> dict[str, Any]:
    bindings = {
        "claim_digest": "sha256:" + "1" * 64,
        "semantics_digest": "sha256:" + "2" * 64,
        "candidate_digest": "sha256:" + "3" * 64,
        "scope_digest": "sha256:" + "4" * 64,
        "encoding_digest": None,
    }
    return {
        "request_version": "1",
        "claim": {
            "artifact_uri": "artifact://sha256/" + "5" * 64,
            "payload": {
                "predicate": "finite_partition",
                "require_disjoint": True,
            },
        },
        "candidate": {"payload": {"cases": cases}},
        "scope": {"payload": {"elements": ["a", "b", "c", "d"]}},
        "certificate": {
            "payload": {
                "certificate_type": "finite.partition",
                "format_version": "1",
                "bindings": bindings,
                "payload": {
                    "relation_id": "case.relation.partitions",
                    "obligation_uri": "artifact://sha256/" + "5" * 64,
                },
            }
        },
        "expected_bindings": bindings,
    }


def test_finite_partition_checker_accepts_exact_partition() -> None:
    decision = check_partition(
        _request(
            cases=[
                {"case_id": "left", "members": ["a", "b"]},
                {"case_id": "right", "members": ["c", "d"]},
            ]
        )
    )

    assert decision["accepted"] is True
    assert decision["coverage"] == "EXHAUSTIVE"
    assert decision["method"] == "EXHAUSTIVE_FINITE"


def test_finite_partition_checker_rejects_gap_and_overlap() -> None:
    gap = check_partition(
        _request(cases=[{"case_id": "only", "members": ["a", "b", "c"]}])
    )
    overlap = check_partition(
        _request(
            cases=[
                {"case_id": "first", "members": ["a", "b", "c"]},
                {"case_id": "second", "members": ["c", "d"]},
            ]
        )
    )

    assert gap["accepted"] is False
    assert "cover" in gap["detail"]
    assert overlap["accepted"] is False
    assert "overlap" in overlap["detail"]


def test_finite_partition_checker_rejects_unbound_relationship_metadata() -> None:
    request = _request(
        cases=[
            {"case_id": "left", "members": ["a", "b"]},
            {"case_id": "right", "members": ["c", "d"]},
        ]
    )
    request["certificate"]["payload"]["payload"]["obligation_uri"] = (
        "artifact://sha256/" + "9" * 64
    )

    decision = check_partition(request)

    assert decision["accepted"] is False
    assert "relationship metadata" in decision["detail"]
