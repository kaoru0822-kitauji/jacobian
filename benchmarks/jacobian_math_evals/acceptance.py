"""Reproducible acceptance helpers for generated suites and Harbor results."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REWARD_KEYS = frozenset(
    {
        "correctness",
        "evidence_validity",
        "scope_accuracy",
        "assurance_calibration",
        "reward",
    }
)


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def validate_oracle_job(
    job_dir: Path,
    *,
    expected_task_names: frozenset[str],
) -> dict[str, Any]:
    results: dict[str, dict[str, Any]] = {}
    for path in sorted(job_dir.glob("*/result.json")):
        value: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("task_name"), str):
            continue
        results[value["task_name"]] = value
    missing = expected_task_names - results.keys()
    unexpected = results.keys() - expected_task_names
    if missing or unexpected:
        raise ValueError(
            f"Oracle task mismatch: missing={sorted(missing)}, "
            f"unexpected={sorted(unexpected)}"
        )
    for task_name, result in results.items():
        if result.get("exception_info") is not None:
            raise ValueError(f"Oracle exception for {task_name}")
        verifier = result.get("verifier_result")
        rewards = verifier.get("rewards") if isinstance(verifier, dict) else None
        if not isinstance(rewards, dict) or set(rewards) != REWARD_KEYS:
            raise ValueError(f"Oracle reward dimensions missing for {task_name}")
        if any(value != 1.0 for value in rewards.values()):
            raise ValueError(f"Oracle did not receive full reward for {task_name}")
    return {
        "task_count": len(results),
        "task_names": sorted(results),
        "all_rewards": 1.0,
    }
