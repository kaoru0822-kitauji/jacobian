from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.validation.agent_workflow_v1 import support

TASK = "integer-perturbation-domain-audit"


def test_oracle_passes(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    accepted = support._run_verifier(task, app, logs)
    assert accepted["reward"] == pytest.approx(1.0)


def test_accepts_alternative_periodic_witness(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = json.loads((app / "submission.json").read_text())
    witness = submission["result"]["integer_witness"]
    witness.update(
        {
            "period": 5,
            "a_values": [3, 4, 6, 8, 9],
            "b_values": [-3, 2, -6, -1, 4],
            "sum_values": [0, 6, 0, 7, 13],
            "b_min": -6,
            "b_max": 4,
            "cancellation_indices": [0, 2],
        }
    )
    support._bind_result_evidence(app, submission)
    support._write_json(app / "submission.json", submission)
    accepted = support._run_verifier(task, app, logs)
    assert accepted["reward"] == pytest.approx(1.0)


def test_rejects_missing_cancellation(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = json.loads((app / "submission.json").read_text())
    submission["result"]["integer_witness"]["cancellation_indices"] = [0]
    support._bind_result_evidence(app, submission)
    support._write_json(app / "submission.json", submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0 and rejected["reward"] == 0.0


def test_rejects_noninteger_domain_shortcut(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = json.loads((app / "submission.json").read_text())
    submission["result"]["integer_witness"]["b_values"][0] = 0
    support._bind_result_evidence(app, submission)
    support._write_json(app / "submission.json", submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0 and rejected["reward"] == 0.0
