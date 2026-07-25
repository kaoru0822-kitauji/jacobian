"""Deliberately simple untrusted plugin entrypoints."""

from __future__ import annotations

import copy
import os
import subprocess
import sys
import time
from typing import Any


def echo(request: dict[str, Any]) -> dict[str, Any]:
    print("untrusted plugin diagnostic")
    return {"seen": request}


def wait_forever(_request: dict[str, Any]) -> dict[str, Any]:
    time.sleep(60)
    return {"unreachable": True}


def exit_without_response(_request: dict[str, Any]) -> dict[str, Any]:
    os._exit(0)


def imitate_source_change(_request: dict[str, Any]) -> dict[str, Any]:
    raise ValueError("plugin source changed during execution")


def emit_large_diagnostic(_request: dict[str, Any]) -> dict[str, Any]:
    print("x" * 4096)
    time.sleep(60)
    return {"status": "otherwise valid"}


def spawn_delayed_child(request: dict[str, Any]) -> dict[str, Any]:
    marker = request["marker"]
    script = (
        "import pathlib,time;"
        "time.sleep(1);"
        f"pathlib.Path({marker!r}).write_text('survived', encoding='utf-8')"
    )
    subprocess.Popen([sys.executable, "-c", script])
    time.sleep(60)
    return {"unreachable": True}


def spawn_child_then_return(request: dict[str, Any]) -> dict[str, Any]:
    """Exit the worker while a descendant still owns its output pipes."""

    marker = request["marker"]
    delay_seconds = request.get("delay_seconds", 1)
    script = (
        "import pathlib,time;"
        f"time.sleep({delay_seconds!r});"
        f"pathlib.Path({marker!r}).write_text('survived', encoding='utf-8')"
    )
    subprocess.Popen([sys.executable, "-c", script])
    return {"worker": "returned"}


def spawn_detached_child_then_return(request: dict[str, Any]) -> dict[str, Any]:
    marker = request["marker"]
    script = (
        "import pathlib,time;"
        "time.sleep(1);"
        f"pathlib.Path({marker!r}).write_text('survived', encoding='utf-8')"
    )
    subprocess.Popen(
        [sys.executable, "-c", script],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return {"worker": "returned"}


def evaluate_candidate(request: dict[str, Any]) -> dict[str, Any]:
    value = request["candidate"]["value"]
    return {
        "conclusion": "FALSE" if value == 3 else "UNKNOWN",
        "arithmetic": "EXACT_INTEGER",
        "method": "EXHAUSTIVE_FINITE",
        "coverage": "EXHAUSTIVE",
        "objectives": {"violations": "1" if value == 3 else "0"},
        "features": {"value": str(value)},
        "failure_classifications": (["fixture_violation"] if value == 3 else []),
        "detail": "fixture evaluation",
    }


def enumerate_invalid_candidate(_request: dict[str, Any]) -> dict[str, Any]:
    """Return a complete page whose candidate violates the installed schema."""

    return {
        "response_version": "1",
        "candidates": [{"not": "a matrix"}],
        "next_cursor": None,
        "complete": True,
        "scope": {"fixture": "invalid candidate"},
    }


def find_fixture_witness(request: dict[str, Any]) -> dict[str, Any]:
    value = request["candidate"]["value"]
    return {
        "status": "FOUND",
        "witness": {"observed": str(value)},
        "witness_format": "fixture.value",
        "format_version": "1",
        "role": request["witness_role"],
        "arithmetic": "EXACT_INTEGER",
        "coverage": "NOT_APPLICABLE",
        "detail": "direct fixture witness",
    }


def propose_fixture_values(request: dict[str, Any]) -> dict[str, Any]:
    cursor = int(request["state"].get("cursor", 0))
    batch_size = int(request["batch_size"])
    stop = min(4, cursor + batch_size)
    return {
        "response_version": "1",
        "candidates": [{"value": value} for value in range(cursor, stop)],
        "state": {"cursor": stop},
        "complete": stop == 4,
        "detail": "finite fixture proposal",
    }


def refine_fixture_search(request: dict[str, Any]) -> dict[str, Any]:
    feedback = request["feedback"]
    nominations = (
        [
            {
                "candidate_uri": feedback[0]["candidate_uri"],
                "reason": "first candidate in the evaluated batch",
            }
        ]
        if feedback
        else []
    )
    return {
        "response_version": "1",
        "state": request["state"],
        "nominations": nominations,
        "detail": "fixture refinement",
    }


def refine_from_verified_counterexample(request: dict[str, Any]) -> dict[str, Any]:
    feedback = request["feedback"]
    return {
        "response_version": "1",
        "state": {
            **request["state"],
            "saw_verified_counterexample": any(
                item["counterexample_verified"] for item in feedback
            ),
        },
        "nominations": [],
        "detail": "recorded independently verified feedback only",
    }


def propose_fixture_values_slowly(request: dict[str, Any]) -> dict[str, Any]:
    time.sleep(0.15)
    return propose_fixture_values(request)


def propose_search_forever(_request: dict[str, Any]) -> dict[str, Any]:
    time.sleep(60)
    return {"unreachable": True}


def propose_malformed_search(_request: dict[str, Any]) -> dict[str, Any]:
    return {
        "response_version": "1",
        "candidates": [],
        "state": {},
        "complete": False,
    }


def propose_declared_failure(_request: dict[str, Any]) -> dict[str, Any]:
    raise RuntimeError("declared fixture failure")


def propose_large_search_output(_request: dict[str, Any]) -> dict[str, Any]:
    return {
        "response_version": "1",
        "candidates": [{"value": 0}],
        "state": {"padding": "x" * 4096},
        "complete": True,
    }


def propose_beyond_authority(_request: dict[str, Any]) -> dict[str, Any]:
    return {
        "response_version": "1",
        "candidates": [{"value": 0}, {"value": 1}],
        "state": {"cursor": 2},
        "complete": True,
    }


def propose_partially_invalid_search(_request: dict[str, Any]) -> dict[str, Any]:
    return {
        "response_version": "1",
        "candidates": [{"value": 1}, {"not_value": 2}],
        "state": {},
        "complete": True,
    }


def refine_with_verification_claim(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "response_version": "1",
        "state": request["state"],
        "nominations": [],
        "verification": "VERIFIED",
    }


def transform_fixture_hypothesis(request: dict[str, Any]) -> dict[str, Any]:
    source = request["source"]
    operation = request["operation"]
    claim = (
        copy.deepcopy(request["constraints"]["claim_template"])
        if operation == "PARAMETER_GENERALIZE"
        else copy.deepcopy(source["payload"])
    )
    parameters = claim["predicate"].setdefault("parameters", {})
    parameters["hypothesis_operation"] = operation.lower()
    proposal: dict[str, Any] = {
        "claim": claim,
        "edit": {
            "kind": operation.lower(),
            "description": "record the fixture hypothesis operation",
            "path": "/predicate/parameters/hypothesis_operation",
            "before": None,
            "after": operation.lower(),
        },
        "metrics": {"fixture_rank": "1"},
        "detail": "fixture hypothesis",
    }
    if operation == "PARAMETER_GENERALIZE":
        proposal["parameter_region"] = {
            "kind": request["constraints"].get("region_kind", "SUFFICIENT"),
            "conditions": {"n": {"minimum": "1"}},
            "evidence": "SAMPLED",
            "sample_uris": [request["evidence"][-1]["artifact_uri"]],
        }
    proposals = (
        [proposal, copy.deepcopy(proposal)] if operation == "GENERATE" else [proposal]
    )
    return {
        "response_version": "1",
        "proposals": proposals,
        "state": {"operation": operation},
        "complete": True,
        "detail": "fixture hypothesis transformation",
    }


def transform_with_unsupported_region_promotion(
    request: dict[str, Any],
) -> dict[str, Any]:
    source = request["source"]
    return {
        "response_version": "1",
        "proposals": [
            {
                "claim": source["payload"],
                "edit": {
                    "kind": "parameter",
                    "description": "unsupported promotion attempt",
                },
                "parameter_region": {
                    "kind": "SUFFICIENT",
                    "conditions": {"n": {"minimum": "1"}},
                    "evidence": "VERIFIED_SUFFICIENT",
                    "subject_uri": request["evidence"][0]["artifact_uri"],
                    "verification_record_uri": (request["evidence"][0]["artifact_uri"]),
                },
            }
        ],
        "state": {},
        "complete": True,
    }


def transform_with_unbound_region_sample(
    request: dict[str, Any],
) -> dict[str, Any]:
    response = transform_fixture_hypothesis(request)
    for proposal in response["proposals"]:
        proposal["parameter_region"] = {
            "kind": "SUFFICIENT",
            "conditions": {"n": {"minimum": "1"}},
            "evidence": "SAMPLED",
            "sample_uris": [request["constraints"]["sample_uri"]],
        }
    return response


def reduce_positive_value(request: dict[str, Any]) -> dict[str, Any]:
    value = request["target"]["value"]
    return {
        "response_version": "1",
        "current_objectives": {"value": str(value)},
        "reductions": (
            [
                {
                    "reducer": "decrement",
                    "payload": {"value": value - 1},
                    "objectives": {"value": str(value - 1)},
                }
            ]
            if value > 0
            else []
        ),
        "detail": "decrement integer candidate",
    }


def reduce_without_improvement(request: dict[str, Any]) -> dict[str, Any]:
    value = request["target"]["value"]
    return {
        "response_version": "1",
        "current_objectives": {"value": str(value)},
        "reductions": [
            {
                "reducer": "decrement",
                "payload": {"value": value},
                "objectives": {"value": str(value)},
            }
        ],
        "detail": "non-improving fixture proposal",
    }


def reduce_once_then_claim_complete(request: dict[str, Any]) -> dict[str, Any]:
    value = request["target"]["value"]
    return {
        "response_version": "1",
        "current_objectives": {"value": str(value)},
        "reductions": (
            [
                {
                    "reducer": "decrement",
                    "payload": {"value": value - 1},
                    "objectives": {"value": str(value - 1)},
                }
            ]
            if value > 2
            else []
        ),
        "detail": "claims completion after one reduction",
    }


def preserve_positive(request: dict[str, Any]) -> dict[str, Any]:
    reduced = request["reduced"]["payload"]["value"]
    return {
        "accepted": reduced >= 1,
        "conclusion": "FALSE" if reduced >= 1 else "UNKNOWN",
        "arithmetic": "EXACT_INTEGER",
        "method": "EXHAUSTIVE_FINITE",
        "coverage": "EXHAUSTIVE",
        "detail": "value remains positive" if reduced >= 1 else "value is not positive",
    }


def preserve_positive_except_failed_boundary(
    request: dict[str, Any],
) -> dict[str, Any]:
    if (
        request["original"]["payload"]["value"] == 2
        and request["reduced"]["payload"]["value"] == 1
    ):
        raise RuntimeError("fixture checker failed at the reduction boundary")
    return preserve_positive(request)
