"""Independent checker entrypoints used by orchestration integration tests."""

from __future__ import annotations

from typing import Any


def check_fixture_value(request: dict[str, Any]) -> dict[str, Any]:
    witness = request["witness"]["payload"]
    candidate = request["candidate"]["payload"]
    role = witness.get("role")
    accepted = (
        request.get("request_version") == "1"
        and witness.get("witness_format") == "fixture.value"
        and witness.get("format_version") == "1"
        and role
        in {
            "DEFEATS_CANDIDATE",
            "REFUTES_CLAIM",
            "RESCUES_CANDIDATE",
            "SUPPORTS_CLAIM",
        }
        and witness.get("bindings") == request.get("expected_bindings")
        and witness.get("payload", {}).get("observed") == str(candidate.get("value"))
    )
    return {
        "accepted": accepted,
        "conclusion": (
            "FALSE"
            if accepted and role in {"DEFEATS_CANDIDATE", "REFUTES_CLAIM"}
            else ("TRUE" if accepted else "UNKNOWN")
        ),
        "arithmetic": "EXACT_INTEGER",
        "method": "DIRECT_WITNESS",
        "coverage": "NOT_APPLICABLE",
        "detail": (
            "fixture value matches the bound candidate"
            if accepted
            else "fixture witness does not match the bound candidate"
        ),
    }


def check_fixture_value_as_true(request: dict[str, Any]) -> dict[str, Any]:
    decision = check_fixture_value(request)
    if decision["accepted"]:
        decision["conclusion"] = "TRUE"
    return decision
