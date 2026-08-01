from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SPIKE = runpy.run_path(
    str(
        PROJECT_ROOT / "benchmarks" / "tasks" / "lean-repl" / "environment" / "spike.py"
    )
)


def test_repl_error_extraction_covers_protocol_and_lean_messages() -> None:
    response_errors = cast(Any, SPIKE["_response_errors"])

    assert response_errors({"message": "Unknown proof state."}) == [
        "Unknown proof state."
    ]
    assert response_errors(
        {
            "messages": [
                {"severity": "warning", "data": "declaration uses sorry"},
                {"severity": "error", "data": "type mismatch"},
            ]
        }
    ) == ["type mismatch"]
