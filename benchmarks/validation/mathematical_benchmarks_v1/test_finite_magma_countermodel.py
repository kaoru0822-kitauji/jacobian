from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.validation.mathematical_benchmarks_v1 import support

TASK = "finite-magma-countermodel"


def test_oracle_certificate_is_accepted(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    accepted = support._run_verifier(task, app, logs)
    assert accepted.details["protocol_compliance"] == 1.0
    assert accepted.details["input_binding"] == 1.0
    assert accepted.details["correctness"] == 1.0
    assert accepted.reward == pytest.approx(1.0)


def test_accepts_alternate_smallest_countermodel(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = json.loads((app / "submission.json").read_text())
    submission["result"]["table"] = [[1, 0], [1, 0]]
    support._bind_result_evidence(app, submission)
    support._write_json(app / "submission.json", submission)

    accepted = support._run_verifier(task, app, logs)
    assert accepted.details["correctness"] == 1.0
    assert accepted.reward == pytest.approx(1.0)


def test_rejects_corrupted_table(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = json.loads((app / "submission.json").read_text())
    submission["result"]["table"][1][1] = 2
    support._write_json(app / "submission.json", submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected.details["input_binding"] == 1.0
    assert rejected.details["correctness"] == 0.0
    assert rejected.reward == 0.0


def test_input_tamper_preserves_mathematical_diagnostic(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    (app / "input.json").write_text("{}")

    rejected = support._run_verifier(task, app, logs)
    assert rejected.details["protocol_compliance"] == 1.0
    assert rejected.details["input_binding"] == 0.0
    assert rejected.details["correctness"] == 1.0
    assert rejected.details["evidence_validity"] == 1.0
    assert rejected.details["scope_accuracy"] == 1.0
    assert rejected.reward == 0.0
