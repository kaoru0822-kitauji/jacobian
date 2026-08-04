from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.validation.agent_workflow_v1 import support

TASK = "extremal-subset-sum-semantic-audit"


def test_accepts_alternative_exact_certificates(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = json.loads((app / "submission.json").read_text())
    submission["result"]["shadowing_certificate"] = {
        "target": 1,
        "first_multiplier": 3,
        "second_multiplier": 1,
        "first_extremum": 3,
        "second_extremum": 0,
    }
    submission["result"]["predicate_certificate"]["intended_witness"] = [2, 3]
    support._bind_result_evidence(app, submission)
    support._write_json(app / "submission.json", submission)
    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_rejects_same_shadow_extremum(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = json.loads((app / "submission.json").read_text())
    submission["result"]["shadowing_certificate"]["second_multiplier"] = 1
    submission["result"]["shadowing_certificate"]["second_extremum"] = 0
    support._write_json(app / "submission.json", submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_rejects_nonoptimal_intended_witness(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = json.loads((app / "submission.json").read_text())
    submission["result"]["predicate_certificate"]["intended_witness"] = [2]
    support._write_json(app / "submission.json", submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_rejects_blocker_outside_legacy_candidate(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = json.loads((app / "submission.json").read_text())
    submission["result"]["predicate_certificate"]["legacy_witness"] = [2, 3]
    support._write_json(app / "submission.json", submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0
