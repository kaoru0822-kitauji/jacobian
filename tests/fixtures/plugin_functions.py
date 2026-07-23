"""Deliberately simple untrusted plugin entrypoints."""

from __future__ import annotations

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


def emit_large_diagnostic(_request: dict[str, Any]) -> dict[str, Any]:
    print("x" * 4096)
    time.sleep(3)
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
    script = (
        "import pathlib,time;"
        "time.sleep(1);"
        f"pathlib.Path({marker!r}).write_text('survived', encoding='utf-8')"
    )
    subprocess.Popen([sys.executable, "-c", script])
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
