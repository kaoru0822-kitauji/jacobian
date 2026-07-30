from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.jacobian_math_evals.acceptance import (
    tree_digest,
    validate_oracle_job,
)


def _write_result(
    root: Path, *, reward: float = 1.0, trial_name: str = "trial"
) -> None:
    trial = root / trial_name
    trial.mkdir(parents=True, exist_ok=True)
    (trial / "result.json").write_text(
        json.dumps(
            {
                "task_name": "jacobian-evals/exact-answer-a-b",
                "exception_info": None,
                "verifier_result": {
                    "rewards": {
                        "correctness": reward,
                        "evidence_validity": 1.0,
                        "scope_accuracy": 1.0,
                        "assurance_calibration": 1.0,
                        "reward": reward,
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_tree_digest_binds_paths_and_bytes(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "x").write_text("same")
    (second / "x").write_text("same")
    assert tree_digest(first) == tree_digest(second)
    (second / "x").write_text("changed")
    assert tree_digest(first) != tree_digest(second)


def test_oracle_acceptance_requires_every_dimension_at_one(
    tmp_path: Path,
) -> None:
    expected = frozenset({"jacobian-evals/exact-answer-a-b"})
    _write_result(tmp_path)
    assert (
        validate_oracle_job(tmp_path, expected_task_names=expected)["task_count"] == 1
    )
    _write_result(tmp_path, reward=0.9)
    with pytest.raises(ValueError, match="full reward"):
        validate_oracle_job(tmp_path, expected_task_names=expected)


def test_oracle_acceptance_rejects_duplicate_task_results(tmp_path: Path) -> None:
    _write_result(tmp_path, trial_name="trial-1")
    _write_result(tmp_path, trial_name="trial-2")
    with pytest.raises(ValueError, match="duplicate Oracle result"):
        validate_oracle_job(
            tmp_path,
            expected_task_names=frozenset({"jacobian-evals/exact-answer-a-b"}),
        )
