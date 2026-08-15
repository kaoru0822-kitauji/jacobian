from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.validation.mathematical_benchmarks_v1 import support

TASK = "rational-linear-solution"


def _run_with_assurance(tmp_path: Path, claimed_assurance: str):
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = json.loads((app / "submission.json").read_text())
    submission["claimed_assurance"] = claimed_assurance
    support._write_json(app / "submission.json", submission)
    return support._run_verifier(task, app, logs)


def test_computed_assurance_receives_full_reward(tmp_path: Path) -> None:
    accepted = _run_with_assurance(tmp_path, "COMPUTED")
    assert accepted.details["correctness"] == 1.0
    assert accepted.details["evidence_validity"] == 1.0
    assert accepted.details["scope_accuracy"] == 1.0
    assert accepted.details["assurance_calibration"] == 1.0
    assert accepted.details["false_certification"] is False
    assert accepted.reward == 1.0


def test_unverified_assurance_retains_lower_assurance_credit(tmp_path: Path) -> None:
    accepted = _run_with_assurance(tmp_path, "UNVERIFIED")
    assert accepted.details["correctness"] == 1.0
    assert accepted.details["evidence_validity"] == 1.0
    assert accepted.details["scope_accuracy"] == 1.0
    assert accepted.details["assurance_calibration"] == 0.0
    assert accepted.details["false_certification"] is False
    assert accepted.reward == pytest.approx(0.9)


def test_checked_overclaim_is_a_hard_zero_with_diagnostics(tmp_path: Path) -> None:
    rejected = _run_with_assurance(tmp_path, "CHECKED")
    assert rejected.details["correctness"] == 1.0
    assert rejected.details["evidence_validity"] == 1.0
    assert rejected.details["scope_accuracy"] == 1.0
    assert rejected.details["assurance_calibration"] == 0.0
    assert rejected.details["false_certification"] is False
    assert rejected.reward == 0.0


def test_verified_overclaim_is_false_certification(tmp_path: Path) -> None:
    rejected = _run_with_assurance(tmp_path, "VERIFIED")
    assert rejected.details["correctness"] == 1.0
    assert rejected.details["evidence_validity"] == 1.0
    assert rejected.details["scope_accuracy"] == 1.0
    assert rejected.details["assurance_calibration"] == 0.0
    assert rejected.details["false_certification"] is True
    assert rejected.reward == 0.0
