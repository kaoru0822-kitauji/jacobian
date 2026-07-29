from __future__ import annotations

from copy import deepcopy
from typing import Any

from jacobian_checkers.polynomial_systems import check_solution


def _request() -> dict[str, Any]:
    bindings = {
        "claim_digest": "sha256:" + "1" * 64,
        "semantics_digest": "sha256:" + "2" * 64,
        "candidate_digest": "sha256:" + "3" * 64,
        "scope_digest": "sha256:" + "4" * 64,
        "encoding_digest": None,
    }
    system_uri = "artifact://sha256/" + "5" * 64
    assignment_uri = "artifact://sha256/" + "6" * 64
    return {
        "request_version": "1",
        "claim": {
            "payload": {
                "claim_schema_version": "1",
                "predicate": "ASSIGNMENT_SATISFIES_POLYNOMIAL_SYSTEM",
                "domain": "QQ",
                "system_uri": system_uri,
                "assignment_uri": assignment_uri,
            }
        },
        "scope": {
            "artifact_uri": system_uri,
            "payload": {
                "system_schema_version": "1",
                "domain": "QQ",
                "variables": ["x"],
                "equations": [
                    {
                        "terms": [
                            {
                                "coefficient": {"num": "1", "den": "1"},
                                "exponents": [2],
                            },
                            {
                                "coefficient": {"num": "-4", "den": "1"},
                                "exponents": [0],
                            },
                        ]
                    }
                ],
                "inequations": [
                    {
                        "terms": [
                            {
                                "coefficient": {"num": "1", "den": "1"},
                                "exponents": [1],
                            }
                        ]
                    }
                ],
            },
        },
        "candidate": {
            "artifact_uri": assignment_uri,
            "payload": {
                "assignment_schema_version": "1",
                "values": [{"num": "2", "den": "1"}],
            },
        },
        "certificate": {
            "payload": {
                "certificate_type": "polynomial.system_solution_replay",
                "format_version": "1",
                "bindings": deepcopy(bindings),
                "payload": {
                    "method": "DIRECT_EXACT_EVALUATION",
                    "system_uri": system_uri,
                    "assignment_uri": assignment_uri,
                    "equation_residuals": [{"num": "0", "den": "1"}],
                    "inequation_values": [{"num": "2", "den": "1"}],
                },
            }
        },
        "expected_bindings": deepcopy(bindings),
    }


def test_solution_checker_accepts_a_valid_assignment() -> None:
    decision = check_solution(_request())

    assert decision["accepted"] is True
    assert decision["conclusion"] == "TRUE"
    assert decision["relation_id"] == "polynomial.relation.satisfies-system"
    assert decision["relationship_source_artifact_uris"] == [
        "artifact://sha256/" + "6" * 64
    ]
    assert decision["relationship_target_artifact_uris"] == [
        "artifact://sha256/" + "5" * 64
    ]
    assert "obligation_uri" not in decision


def test_solution_checker_verifies_a_violating_assignment_as_false() -> None:
    request = _request()
    request["candidate"]["payload"]["values"][0] = {"num": "1", "den": "1"}
    request["certificate"]["payload"]["payload"]["equation_residuals"] = [
        {"num": "-3", "den": "1"}
    ]
    request["certificate"]["payload"]["payload"]["inequation_values"] = [
        {"num": "1", "den": "1"}
    ]

    decision = check_solution(request)

    assert decision["accepted"] is True
    assert decision["conclusion"] == "FALSE"
    assert "relation_id" not in decision
    assert "relationship_source_artifact_uris" not in decision
    assert "relationship_target_artifact_uris" not in decision
    assert "obligation_uri" not in decision


def test_solution_checker_rejects_assignment_substitution() -> None:
    request = _request()
    request["candidate"]["artifact_uri"] = "artifact://sha256/" + "9" * 64

    decision = check_solution(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_solution_checker_rejects_misreported_residuals() -> None:
    request = _request()
    request["certificate"]["payload"]["payload"]["equation_residuals"][0] = {
        "num": "1",
        "den": "1",
    }

    decision = check_solution(request)

    assert decision["accepted"] is False
    assert decision["conclusion"] == "UNKNOWN"


def test_solution_checker_rejects_noncanonical_rational() -> None:
    request = _request()
    request["candidate"]["payload"]["values"][0] = {"num": "2", "den": "2"}

    decision = check_solution(request)

    assert decision["accepted"] is False
