from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.validation.agent_workflow_v1 import support

TASK = "metamath-syllogism-repair"


def _bind(app: Path, submission: dict) -> None:
    support._bind_result_evidence(app, submission)
    support._write_json(app / "submission.json", submission)


def test_metamath_repair_accepts_oracle(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    "mutation",
    ["proof", "positions", "trace", "substitution", "target", "assurance", "evidence"],
)
def test_metamath_repair_rejects_tampering(tmp_path: Path, mutation: str) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    submission = json.loads((app / "submission.json").read_text())
    if mutation == "proof":
        submission["result"]["repaired_proof"][6] = "a1i"
    elif mutation == "positions":
        submission["result"]["changed_positions"] = [5, 9]
    elif mutation == "trace":
        submission["result"]["trace"][6]["stack_depth"] += 1
    elif mutation == "substitution":
        submission["result"]["trace"][9]["substitution"]["u"] = ["u"]
    elif mutation == "target":
        submission["result"]["final_expression"][-2] = "v"
    elif mutation == "assurance":
        submission["claimed_assurance"] = "VERIFIED"
    elif mutation == "evidence":
        submission["evidence"][0]["sha256"] = "sha256:" + "0" * 64
    if mutation != "evidence":
        _bind(app, submission)
    else:
        support._write_json(app / "submission.json", submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["reward"] == 0.0


def test_metamath_repair_rejects_frozen_input_tamper(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(tmp_path, TASK, "computed")
    frozen = json.loads((app / "input.json").read_text())
    frozen["target"][-2] = "v"
    support._write_json(app / "input.json", frozen)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["reward"] == 0.0
