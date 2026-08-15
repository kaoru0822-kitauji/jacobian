from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.validation.mathematical_benchmarks_v1 import support

TASK = "calendar-good-days-audit"


def test_rejects_corrupted_count(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = json.loads((app / "submission.json").read_text())
    submission["result"]["count"] = 15
    support._write_json(app / "submission.json", submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected.details["correctness"] == 0.0
    assert rejected.reward == 0.0


@pytest.mark.parametrize("claimed_assurance", ["CHECKED", "VERIFIED"])
def test_rejects_assurance_overclaim_without_erasing_math_diagnostic(
    tmp_path: Path,
    claimed_assurance: str,
) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = json.loads((app / "submission.json").read_text())
    submission["claimed_assurance"] = claimed_assurance
    support._write_json(app / "submission.json", submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected.details["correctness"] == 1.0
    assert rejected.details["protocol_compliance"] == 0.0
    assert rejected.details["assurance_calibration"] == 0.0
    assert rejected.reward == 0.0
    assert rejected.details["false_certification"] is (claimed_assurance == "VERIFIED")


def test_tampered_input_is_a_hard_gate_without_erasing_math_diagnostic(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    input_data = json.loads((app / "input.json").read_text())
    input_data["task_id"] = "tampered"
    support._write_json(app / "input.json", input_data)

    rejected = support._run_verifier(task, app, logs)
    assert rejected.details["correctness"] == 1.0
    assert rejected.details["protocol_compliance"] == 1.0
    assert rejected.details["input_binding"] == 0.0
    assert rejected.reward == 0.0
