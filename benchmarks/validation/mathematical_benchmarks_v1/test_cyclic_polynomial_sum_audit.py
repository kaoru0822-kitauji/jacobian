from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.validation.mathematical_benchmarks_v1 import support

TASK = "cyclic-polynomial-sum-audit"


def _case(tmp_path: Path):
    return support._prepare_case(tmp_path, TASK, "computed")


def test_oracle_replays_complete_elimination_certificate(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    accepted = support._run_verifier(task, app, logs)
    assert accepted.details["correctness"] == 1.0
    assert accepted.reward == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("necessary_polynomial", 2), -10),
        (("proposed_evaluations", 1), "0"),
        (("excluded_branch", "product"), "-111/8"),
        (("excluded_branch", "residual"), "0"),
    ],
)
def test_rejects_corrupted_algebraic_certificates(
    tmp_path: Path, path: tuple[object, ...], replacement: object
) -> None:
    task, app, logs = _case(tmp_path)
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    target = submission["result"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected.details["correctness"] == 0.0
    assert rejected.reward == 0.0


def test_rejects_unearned_verified_claim(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["claimed_assurance"] = "VERIFIED"
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected.reward == 0.0
    assert rejected.details["false_certification"] is True


@pytest.mark.parametrize("claimed_assurance", ["CHECKED", "VERIFIED"])
def test_rejects_above_ceiling_assurance_without_erasing_diagnostics(
    tmp_path: Path,
    claimed_assurance: str,
) -> None:
    task, app, logs = _case(tmp_path)
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["claimed_assurance"] = claimed_assurance
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected.details["correctness"] == 1.0
    assert rejected.details["evidence_validity"] == 1.0
    assert rejected.details["scope_accuracy"] == 1.0
    assert rejected.details["assurance_calibration"] == 0.0
    assert rejected.reward == 0.0
    assert rejected.details["false_certification"] is (claimed_assurance == "VERIFIED")


def test_rejects_keyword_filler_evidence(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    evidence_path = app / "evidence" / "cyclic-elimination-certificate.json"
    evidence_path.write_text(
        "pairwise distinct a+b product residual -3/2 " * 64,
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["evidence"][0]["sha256"] = support._digest(evidence_path)
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected.details["correctness"] == 1.0
    assert rejected.details["evidence_validity"] == 0.0
    assert rejected.reward == 0.0


@pytest.mark.parametrize("section", ["result", "limitations"])
def test_rejects_evidence_not_bound_to_submission(
    tmp_path: Path,
    section: str,
) -> None:
    task, app, logs = _case(tmp_path)
    evidence_path = app / "evidence" / "cyclic-elimination-certificate.json"
    evidence = json.loads(evidence_path.read_text())
    if section == "result":
        evidence["result"]["excluded_branch"]["residual"] = "0"
    else:
        evidence["limitations"] = []
    support._write_json(evidence_path, evidence)
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["evidence"][0]["sha256"] = support._digest(evidence_path)
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected.details["correctness"] == 1.0
    assert rejected.details["evidence_validity"] == 0.0
    assert rejected.reward == 0.0


def test_rejects_oversized_evidence_before_parsing(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    evidence_path = app / "evidence" / "cyclic-elimination-certificate.json"
    evidence_path.write_text(" " * (64 * 1024 + 1))
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["evidence"][0]["sha256"] = support._digest(evidence_path)
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected.details["correctness"] == 1.0
    assert rejected.details["evidence_validity"] == 0.0
    assert rejected.reward == 0.0
