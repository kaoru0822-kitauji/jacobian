from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.validation.mathematical_benchmarks_v1 import support

TASK = "domino-profile-transfer-audit"
EVIDENCE = "evidence/profile-transfer-certificate.json"


def _case(tmp_path: Path):
    return support._prepare_case(tmp_path, TASK, "computed")


def _bind_evidence(app: Path, submission: dict) -> None:
    evidence = {
        "schema_version": "1",
        "task_id": submission["task_id"],
        "result": submission["result"],
        "limitations": submission["limitations"],
    }
    evidence_path = app / EVIDENCE
    support._write_json(evidence_path, evidence)
    submission["evidence"][0]["sha256"] = support._digest(evidence_path)


def _matrix_multiply(left: list[list[int]], right: list[list[int]]) -> list[list[int]]:
    return [
        [sum(left[i][k] * right[k][j] for k in range(8)) % 19 for j in range(8)]
        for i in range(8)
    ]


def _vector_multiply(vector: list[int], matrix: list[list[int]]) -> list[int]:
    return [sum(vector[k] * matrix[k][j] for k in range(8)) % 19 for j in range(8)]


def _trace(matrix: list[list[int]], row: int) -> list[dict[str, object]]:
    vector = [0] * 8
    vector[1 << row] = 1
    power = matrix
    trace: list[dict[str, object]] = []
    for bit in range((2021).bit_length()):
        if 2021 & (1 << bit):
            before = vector
            vector = _vector_multiply(vector, power)
            trace.append({"bit": bit, "before": before, "after": vector})
        power = _matrix_multiply(power, power)
    return trace


def test_accepts_reflected_corner_with_independent_trace(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    path = app / "submission.json"
    submission = json.loads(path.read_text())
    matrix = submission["result"]["transition_matrix"]
    submission["result"]["removed_row"] = 2
    submission["result"]["initial_vector"] = [0, 0, 0, 0, 1, 0, 0, 0]
    submission["result"]["exponentiation_trace"] = _trace(matrix, 2)
    _bind_evidence(app, submission)
    support._write_json(path, submission)
    accepted = support._run_verifier(task, app, logs)
    assert accepted.details["correctness"] == 1.0
    assert accepted.reward == pytest.approx(1.0)


@pytest.mark.parametrize("corruption", ["matrix", "trace", "remainder", "initial"])
def test_rejects_corrupted_certificates(tmp_path: Path, corruption: str) -> None:
    task, app, logs = _case(tmp_path)
    path = app / "submission.json"
    submission = json.loads(path.read_text())
    result = submission["result"]
    if corruption == "matrix":
        result["transition_matrix"][0][0] = 1
    elif corruption == "trace":
        result["exponentiation_trace"][3]["after"][0] ^= 1
    elif corruption == "remainder":
        result["remainder"] = 4
    else:
        result["initial_vector"] = [1, 0, 0, 0, 0, 0, 0, 0]
    support._write_json(path, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected.details["correctness"] == 0.0
    assert rejected.reward == 0.0


def test_rejects_unearned_verified_claim(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    path = app / "submission.json"
    submission = json.loads(path.read_text())
    submission["claimed_assurance"] = "VERIFIED"
    support._write_json(path, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected.reward == 0.0
    assert rejected.details["false_certification"] is True


def test_unchanged_oracle_structured_evidence_is_accepted(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    accepted = support._run_verifier(task, app, logs)
    assert accepted.details["correctness"] == 1.0
    assert accepted.details["evidence_validity"] == 1.0
    assert accepted.reward == pytest.approx(1.0)


def test_rejects_keyword_filler_evidence(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    evidence_path = app / EVIDENCE
    evidence_path.write_text("profile transition binary remainder " + "filler " * 50)
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["evidence"][0]["sha256"] = support._digest(evidence_path)
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected.details["correctness"] == 1.0
    assert rejected.details["evidence_validity"] == 0.0
    assert rejected.reward == 0.0


def test_rejects_evidence_result_substitution(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    evidence_path = app / EVIDENCE
    evidence = json.loads(evidence_path.read_text())
    evidence["result"]["remainder"] = 4
    support._write_json(evidence_path, evidence)
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["evidence"][0]["sha256"] = support._digest(evidence_path)
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected.details["correctness"] == 1.0
    assert rejected.details["evidence_validity"] == 0.0
    assert rejected.reward == 0.0


def test_rejects_evidence_limitations_substitution(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    evidence_path = app / EVIDENCE
    evidence = json.loads(evidence_path.read_text())
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


def test_rejects_boolean_integer_alias_in_evidence(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    evidence_path = app / EVIDENCE
    evidence = json.loads(evidence_path.read_text())
    evidence["result"]["remainder"] = True
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
    evidence_path = app / EVIDENCE
    evidence_path.write_bytes(b" " * (64 * 1024 + 1))
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["evidence"][0]["sha256"] = support._digest(evidence_path)
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected.details["correctness"] == 1.0
    assert rejected.details["evidence_validity"] == 0.0
    assert rejected.reward == 0.0


def test_rejects_malformed_evidence_envelope(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    evidence_path = app / EVIDENCE
    evidence_path.write_text("not json")
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["evidence"][0]["sha256"] = support._digest(evidence_path)
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected.details["correctness"] == 1.0
    assert rejected.details["evidence_validity"] == 0.0
    assert rejected.reward == 0.0
