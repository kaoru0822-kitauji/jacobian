from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pytest
from benchmarks.validation.agent_workflow_v1 import support

TASK = "diophantine-ratio-family-repair"


def _case(tmp_path: Path):
    return support._prepare_case(tmp_path, TASK, "computed")


def _rewrite(app: Path, submission: dict) -> None:
    support._bind_result_evidence(app, submission)
    support._write_json(app / "submission.json", submission)


def _compose_with_shift(poly: list[int], shift: int = 1) -> list[int]:
    result = [0] * len(poly)
    for degree, coefficient in enumerate(poly):
        for power in range(degree + 1):
            result[power] += (
                coefficient * math.comb(degree, power) * (shift ** (degree - power))
            )
    while len(result) > 1 and result[-1] == 0:
        result.pop()
    return result


def _probe(family: dict, t: int) -> dict:
    def evaluate(poly: list[int]) -> int:
        value = 0
        for coefficient in reversed(poly):
            value = value * t + coefficient
        return value

    x = evaluate(family["x"])
    y = evaluate(family["y"])
    ratio = evaluate(family["ratio"])
    divisor = x * x - x * y + y * y
    return {
        "t": t,
        "x": x,
        "y": y,
        "divisor": divisor,
        "multiple": x * y * (x * y - 1),
        "ratio": [ratio, 1],
    }


def test_accepts_alternative_polynomial_parameterization(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    family = submission["result"]["family"]
    for name, polynomial in family.items():
        family[name] = _compose_with_shift(polynomial)
    submission["result"]["probes"] = [_probe(family, t) for t in (2, 4, 6)]
    _rewrite(app, submission)
    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_rejects_ratio_not_bound_to_pair(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    submission["result"]["family"]["ratio"] = [1]
    _rewrite(app, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_rejects_probe_count_above_public_maximum(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    family = submission["result"]["family"]
    submission["result"]["probes"] = [_probe(family, t) for t in range(2, 9)]
    _rewrite(app, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["protocol_compliance"] == 0.0
    assert rejected["reward"] == 0.0


def test_rejects_polynomial_outside_public_bounds(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    submission["result"]["family"]["a"] = [0] * 13
    _rewrite(app, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_preserves_math_diagnostic_for_envelope_error(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    submission["completeness"] = "PARTIAL"
    _rewrite(app, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["protocol_compliance"] == 0.0
    assert rejected["correctness"] == 1.0
    assert rejected["evidence_validity"] == 1.0
    assert rejected["reward"] == 0.0


def test_rejects_evidence_json_with_json_type_coercion(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    evidence_path = app / "evidence" / "answer.txt"
    result = json.loads(json.dumps(submission["result"]))
    result["probes"][0]["x"] = True
    evidence_path.write_text("RESULT_JSON: " + json.dumps(result) + "\n")
    submission["evidence"][0]["sha256"] = support._digest(evidence_path)
    support._write_json(app / "submission.json", submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["evidence_validity"] == 0.0
    assert rejected["reward"] == 0.0


def test_rejects_deeply_nested_evidence_without_crashing(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    evidence_path = app / "evidence" / "answer.txt"
    evidence_path.write_text("RESULT_JSON: " + ("[" * 10000) + ("]" * 10000))
    submission["evidence"][0]["sha256"] = support._digest(evidence_path)
    support._write_json(app / "submission.json", submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["evidence_validity"] == 0.0
    assert rejected["reward"] == 0.0


def test_rejects_non_regular_visible_input_without_blocking(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    app_input = app / "input.json"
    app_input.unlink()
    os.mkfifo(app_input)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["reward"] == 0.0


def test_rejects_oversized_evidence_before_hashing(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    evidence_path = app / "evidence" / "answer.txt"
    with evidence_path.open("wb") as stream:
        stream.truncate(1_048_577)
    submission["evidence"][0]["sha256"] = "sha256:" + "0" * 64
    support._write_json(app / "submission.json", submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["evidence_validity"] == 0.0
    assert rejected["reward"] == 0.0


@pytest.mark.parametrize(
    ("path", "replacement"),
    [("quotient", [-1, 0, 1]), ("divisibility_quotient", [1]), ("ratio", "t")],
)
def test_rejects_corrupted_family(
    tmp_path: Path, path: str, replacement: object
) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    submission["result"]["family"][path] = replacement
    _rewrite(app, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_rejects_false_vieta_integrality(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    submission["result"]["source_audit"]["status_for_d_ge_2"] = "INTEGER"
    _rewrite(app, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
