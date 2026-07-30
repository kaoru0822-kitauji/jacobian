from __future__ import annotations

import hashlib
import json
import os
import pathlib
import runpy
import shutil
import sys
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).parents[3]
TASKS = ROOT / "benchmarks" / "regression-v1" / "tasks"
VERIFICATION_RECORD_TASKS = (
    "finite-partition",
    "hermite-normal-form",
    "polynomial-map-collision",
    "polynomial-normalization",
    "sat-witness",
)
RATIONAL_TASK = "rational-linear-solution"
RESOURCE_DERIVED_TASKS = (
    "calendar-good-days-audit",
    "euler-line-symbolic-certificate",
    "log-exponent-recovery",
    "matrix-square-zero-counterexample",
    "polynomial-tail-counterexample",
    "random-function-expectation-audit",
    "subspace-direct-sum-counterexample",
)


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _sat_record(task: Path, app: Path, submission: Mapping[str, object]) -> dict:
    input_data = json.loads((task / "input.json").read_text())
    result = submission["result"]
    assert isinstance(result, dict)
    assignment = result["assignment"]
    assert isinstance(assignment, dict)
    key = ",".join("1" if assignment[name] else "0" for name in input_data["variables"])
    authorized = json.loads((task / "tests" / "authorized_records.json").read_text())[
        key
    ]
    return {
        "task_id": input_data["task_id"],
        "input_sha256": _digest(app / "input.json"),
        "conclusion": "TRUE",
        "status": "VERIFIED_SATISFYING",
        "assignment": assignment,
        "scope": submission["scope"],
        "verification_record": authorized,
    }


def _bound_record(task_name: str, task: Path, app: Path, submission: dict) -> dict:
    if task_name == "sat-witness":
        return _sat_record(task, app, submission)
    return json.loads((task / "tests" / "authorized_record.json").read_text())


def _run_verifier(task: Path, app: Path, logs: Path) -> dict:
    concrete_path = type(pathlib.Path())
    original_path = pathlib.Path
    mounts = {
        "/app": app,
        "/tests": task / "tests",
        "/logs/verifier": logs,
    }

    def mapped_path(value: os.PathLike[str] | str = ".") -> Path:
        raw = os.fspath(value)
        for prefix, target in mounts.items():
            if raw == prefix:
                return concrete_path(target)
            if raw.startswith(prefix + "/"):
                return concrete_path(target) / raw.removeprefix(prefix + "/")
        return concrete_path(raw)

    try:
        pathlib.Path = mapped_path  # type: ignore[assignment]
        sys.path.insert(0, str(task / "tests"))
        runpy.run_path(str(task / "tests" / "verifier.py"), run_name="__main__")
    finally:
        sys.path.remove(str(task / "tests"))
        sys.modules.pop("verifier_support", None)
        pathlib.Path = original_path
    return json.loads((logs / "reward.json").read_text())


def _prepare_case(
    tmp_path: Path,
    task_name: str,
    scenario: str,
) -> tuple[Path, Path, Path]:
    task = TASKS / task_name
    root = tmp_path / task_name / scenario
    app = root / "app"
    logs = root / "logs"
    (app / "evidence").mkdir(parents=True)
    logs.mkdir(parents=True)
    shutil.copy2(task / "input.json", app / "input.json")
    shutil.copy2(task / "solution" / "answer.txt", app / "evidence" / "answer.txt")
    submission = json.loads((task / "solution" / "submission.json").read_text())
    submission.pop("verification_record_uri", None)

    if scenario == "computed":
        submission["claimed_assurance"] = "COMPUTED"
    else:
        submission["claimed_assurance"] = "VERIFIED"
    if scenario in {"bound", "invalid"}:
        record = (
            _bound_record(task_name, task, app, submission)
            if scenario == "bound"
            else {}
        )
        record_path = app / "evidence" / "verification-record.json"
        _write_json(record_path, record)
        if scenario == "bound":
            schema = json.loads(
                (task / "environment" / "verification_record_schema.json").read_text()
            )
            Draft202012Validator(schema).validate(record)
        submission["verification_record_uri"] = {
            "path": "evidence/verification-record.json",
            "sha256": _digest(record_path),
        }
    _write_json(app / "submission.json", submission)
    return task, app, logs


@pytest.mark.parametrize("task_name", VERIFICATION_RECORD_TASKS)
def test_verifier_scoring_separates_math_from_verification_record(
    tmp_path: Path,
    task_name: str,
) -> None:
    computed = _run_verifier(*_prepare_case(tmp_path, task_name, "computed"))
    assert computed["correctness"] == 1.0
    assert computed["reward"] == pytest.approx(0.9)
    assert computed["false_certification"] is False

    missing = _run_verifier(*_prepare_case(tmp_path, task_name, "missing"))
    assert missing["correctness"] == 1.0
    assert missing["reward"] == 0.0
    assert missing["false_certification"] is True

    bound = _run_verifier(*_prepare_case(tmp_path, task_name, "bound"))
    assert bound["correctness"] == 1.0
    assert bound["reward"] == pytest.approx(1.0)
    assert bound["false_certification"] is False

    invalid = _run_verifier(*_prepare_case(tmp_path, task_name, "invalid"))
    assert invalid["correctness"] == 1.0
    assert invalid["reward"] == 0.0
    assert invalid["false_certification"] is True


def test_rational_solution_rejects_unsupported_verified_claim(
    tmp_path: Path,
) -> None:
    computed = _run_verifier(*_prepare_case(tmp_path, RATIONAL_TASK, "computed"))
    assert computed["correctness"] == 1.0
    assert computed["reward"] == pytest.approx(1.0)
    assert computed["false_certification"] is False

    for scenario in ("missing", "invalid"):
        result = _run_verifier(*_prepare_case(tmp_path, RATIONAL_TASK, scenario))
        assert result["correctness"] == 1.0
        assert result["reward"] == 0.0
        assert result["false_certification"] is True


@pytest.mark.parametrize("task_name", RESOURCE_DERIVED_TASKS)
def test_resource_derived_oracles_and_assurance_boundary(
    tmp_path: Path,
    task_name: str,
) -> None:
    computed = _run_verifier(*_prepare_case(tmp_path, task_name, "computed"))
    assert computed["correctness"] == 1.0
    assert computed["reward"] == pytest.approx(1.0)
    assert computed["false_certification"] is False

    unsupported = _run_verifier(*_prepare_case(tmp_path, task_name, "missing"))
    assert unsupported["correctness"] == 1.0
    assert unsupported["reward"] == 0.0
    assert unsupported["false_certification"] is True


@pytest.mark.parametrize(
    ("task_name", "mutate"),
    [
        (
            "calendar-good-days-audit",
            lambda result: result.update(count=15),
        ),
        (
            "euler-line-symbolic-certificate",
            lambda result: result["coordinates"]["O"]["x"]["numerator"][0].update(
                coefficient="2"
            ),
        ),
        (
            "matrix-square-zero-counterexample",
            lambda result: result.update(matrix=[[1, 0], [0, 0]]),
        ),
        (
            "polynomial-tail-counterexample",
            lambda result: result.update(x2="1"),
        ),
        (
            "subspace-direct-sum-counterexample",
            lambda result: result.update(dependence_coefficients=[1, 1, 1, 1]),
        ),
        (
            "log-exponent-recovery",
            lambda result: result.update(value=59),
        ),
        (
            "random-function-expectation-audit",
            lambda result: result.update(expected_value="2025"),
        ),
    ],
)
def test_resource_derived_verifiers_reject_corrupted_witnesses(
    tmp_path: Path,
    task_name: str,
    mutate,
) -> None:
    task, app, logs = _prepare_case(tmp_path, task_name, "computed")
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    mutate(submission["result"])
    _write_json(submission_path, submission)

    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_euler_line_verifier_accepts_equivalent_rational_functions(
    tmp_path: Path,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path,
        "euler-line-symbolic-certificate",
        "computed",
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    result = submission["result"]
    for point in result["coordinates"].values():
        for coordinate in point.values():
            for term in coordinate["numerator"]:
                value = Fraction(term["coefficient"]) * 2
                term["coefficient"] = str(value)
            for term in coordinate["denominator"]:
                value = Fraction(term["coefficient"]) * 2
                term["coefficient"] = str(value)
    result["relation_coefficients"] = ["4", "-6", "2"]
    _write_json(submission_path, submission)

    accepted = _run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_euler_line_verifier_rejects_extra_denominator_singularity(
    tmp_path: Path,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path,
        "euler-line-symbolic-certificate",
        "computed",
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["coordinates"]["O"]["x"]["denominator"][0]["exponents"] = [
        1,
        0,
        0,
    ]
    _write_json(submission_path, submission)

    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0
