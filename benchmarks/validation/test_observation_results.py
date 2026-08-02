from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from benchmarks.tooling import observation_results
from benchmarks.tooling.observation_results import (
    build_observation_evidence,
    compare_evidence,
    render_markdown,
)


def _evidence(condition: str, correctness: list[float]) -> dict:
    trials = []
    for repetition, reward in enumerate(correctness):
        trials.append(
            {
                "task": "case",
                "task_digest": "sha256:" + "a" * 64,
                "repetition": repetition,
                "rewards": {
                    "correctness": reward,
                    "evidence_validity": reward,
                    "scope_accuracy": 1.0,
                    "assurance_calibration": 1.0,
                    "reward": reward,
                },
                "false_certification": False,
                "tokens": {"input": 10, "output": 5},
                "cost_usd": 0.01,
                "agent_seconds": 2.0,
            }
        )
    return {
        "status": "VALID",
        "causal_claim_authorized": False,
        "source_sha": "a" * 40,
        "dataset": "agent-workflow-v1",
        "condition": condition,
        "job": {"comparison_signature": "sha256:" + "b" * 64},
        "fixed_invariants": {
            "model": "model",
            "tasks": [{"task": "case", "digest": "sha256:" + "a" * 64}],
            "sampling_seed": None,
            "sampling_deterministic": False,
        },
        "trials": trials,
    }


def test_paired_report_keeps_public_claim_boundary() -> None:
    report = compare_evidence(
        _evidence("control", [0.0, 1.0]), _evidence("treatment", [1.0, 1.0])
    )

    assert report["status"] == "VALID"
    assert report["causal_claim_authorized"] is False
    assert report["metrics"]["correctness"]["paired_delta"] == 0.5
    assert (
        report["metrics"]["correctness"]["interpretation"] == "descriptive-small-sample"
    )
    assert "does not itself authorize a causal" in render_markdown(report)


def test_comparison_rejects_invariant_drift() -> None:
    control = _evidence("control", [1.0])
    treatment = deepcopy(_evidence("treatment", [1.0]))
    treatment["fixed_invariants"]["model"] = "different"

    report = compare_evidence(control, treatment)

    assert report["status"] == "INVALID"
    assert "fixed invariants differ" in report["validation_failures"]


def test_comparison_rejects_unpaired_repetitions() -> None:
    report = compare_evidence(
        _evidence("control", [1.0, 1.0]), _evidence("treatment", [1.0])
    )

    assert report["status"] == "INVALID"
    assert (
        "control/treatment trials do not pair exactly" in report["validation_failures"]
    )


def test_observation_normalization_binds_repetitions_and_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(observation_results, "task_digest", lambda _path: "a" * 64)
    monkeypatch.setattr(observation_results, "_git_sha", lambda: "b" * 40)
    job = {
        "jobs_dir": str(tmp_path / "jobs"),
        "n_attempts": 1,
        "timeout_multiplier": 1,
        "orchestrator": {"type": "local", "n_concurrent_trials": 1},
        "environment": {"type": "docker"},
        "agents": [{"name": "codex"}],
        "datasets": [
            {
                "path": "benchmarks/datasets/agent-workflow-v1",
                "task_names": ["graph-counterexample"],
            }
        ],
    }
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(job), encoding="utf-8")
    result = {
        "id": "job",
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:01:00Z",
        "n_total_trials": 1,
        "stats": {
            "n_completed_trials": 1,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 0,
            "n_cancelled_trials": 0,
        },
        "trial_results": [
            {
                "task_name": "jacobian/graph-counterexample",
                "task_checksum": "sha256:" + "a" * 64,
                "trial_name": "attempt-0",
                "agent_info": {
                    "name": "codex",
                    "version": "1",
                    "model_info": {"name": "model"},
                },
                "agent_result": {
                    "n_input_tokens": 10,
                    "n_output_tokens": 5,
                    "cost_usd": 0.01,
                },
                "verifier_result": {
                    "rewards": {"correctness": 1.0, "false_certification": 0.0}
                },
                "exception_info": None,
            }
        ],
    }
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")

    evidence, failures = build_observation_evidence(
        dataset="agent-workflow-v1",
        condition="control",
        job_path=job_path,
        jobs_dir=tmp_path,
        result_path=result_path,
    )

    assert failures == []
    assert evidence["status"] == "VALID"
    assert evidence["fixed_invariants"]["model"] == "model"
