"""Fail-closed tests for the benchmark workflow plan contract."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
VALIDATOR = ROOT / ".github" / "scripts" / "validate-benchmark-plan"


def _run(plan: dict[str, str]) -> subprocess.CompletedProcess[str]:
    payload = "\n".join(f"{key}={value}" for key, value in plan.items()) + "\n"
    return subprocess.run(
        [sys.executable, str(VALIDATOR)],
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )


def _plan() -> dict[str, str]:
    return {
        "run-benchmark-check": "true",
        "run-benchmark-oracle": "true",
        "benchmark-oracle-scope": "changed-tasks",
        "benchmark-oracle-matrix": json.dumps(
            [
                {
                    "dataset": "suite",
                    "shard": "task",
                    "tasks": ["task"],
                    "task_digests": [{"task": "task", "digest": "sha256:" + "a" * 64}],
                }
            ]
        ),
        "benchmark-plan-reasons": json.dumps(["executable task change"]),
    }


def test_valid_benchmark_plan_is_accepted() -> None:
    result = _run(_plan())

    assert result.returncode == 0, result.stderr


def test_oracle_plan_requires_a_nonempty_matrix() -> None:
    plan = _plan()
    plan["benchmark-oracle-matrix"] = "[]"

    result = _run(plan)

    assert result.returncode != 0
    assert "non-empty matrix" in result.stderr


def test_duplicate_dataset_task_pair_is_rejected() -> None:
    plan = _plan()
    entry = json.loads(plan["benchmark-oracle-matrix"])[0]
    plan["benchmark-oracle-matrix"] = json.dumps([entry, entry])

    result = _run(plan)

    assert result.returncode != 0
    assert "duplicate" in result.stderr
