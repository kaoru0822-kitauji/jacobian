from __future__ import annotations

import hashlib
import json
import os
import pathlib
import runpy
import shutil
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).parents[3]
TASKS = ROOT / "benchmarks" / "datasets" / "agent-workflow-v1" / "tasks"
VERIFICATION_RECORD_TASKS = (
    "finite-partition",
    "hermite-normal-form",
    "polynomial-map-collision",
    "polynomial-normalization",
    "sat-witness",
)
RATIONAL_TASK = "rational-linear-solution"
RESOURCE_DERIVED_TASKS = (
    "autoformalization-semantic-audit",
    "calendar-good-days-audit",
    "finite-magma-countermodel",
    "generated-lemma-vacuity-audit",
    "inverse-distance-remainder-audit",
    "log-exponent-recovery",
    "matrix-square-zero-counterexample",
    "metric-tsp-proof-repair",
    "noncompact-lefschetz-proof-audit",
    "parameterized-sharp-bound-audit",
    "polynomial-tail-counterexample",
    "random-function-expectation-audit",
    "subspace-direct-sum-counterexample",
    "well-total-domination-counterexample",
)
VERIFIER_TASKS = tuple(
    sorted(
        task.parent.name
        for task in TASKS.rglob("task.toml")
        if (task.parent / "tests" / "verifier.py").is_file()
    )
)


def _task_tree_snapshot() -> dict[str, str]:
    return {
        path.relative_to(TASKS).as_posix(): _digest(path)
        for path in sorted(TASKS.rglob("*"))
        if path.is_file()
    }


def _task(task_name: str) -> Path:
    matches = list(TASKS.rglob(task_name))
    assert len(matches) == 1
    return matches[0]


def _digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _bind_result_evidence(app: Path, submission: dict) -> None:
    evidence_path = app / "evidence" / "answer.txt"
    lines = evidence_path.read_text().splitlines()
    marker = "RESULT_JSON: " + json.dumps(
        submission["result"], sort_keys=True, separators=(",", ":")
    )
    evidence_path.write_text(
        "\n".join(marker if line.startswith("RESULT_JSON:") else line for line in lines)
        + "\n"
    )
    submission["evidence"][0]["sha256"] = _digest(evidence_path)


def _sat_record(task: Path, app: Path, submission: Mapping[str, object]) -> dict:
    input_data = json.loads((task / "environment" / "input.json").read_text())
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
    original_dont_write_bytecode = sys.dont_write_bytecode
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
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(task / "tests"))
        runpy.run_path(str(task / "tests" / "verifier.py"), run_name="__main__")
    finally:
        sys.path.remove(str(task / "tests"))
        sys.modules.pop("verifier_support", None)
        sys.dont_write_bytecode = original_dont_write_bytecode
        pathlib.Path = original_path
    return json.loads((logs / "reward.json").read_text())


def _prepare_case(
    tmp_path: Path,
    task_name: str,
    scenario: str,
) -> tuple[Path, Path, Path]:
    task = _task(task_name)
    root = tmp_path / task_name / scenario
    app = root / "app"
    logs = root / "logs"
    (app / "evidence").mkdir(parents=True)
    logs.mkdir(parents=True)
    shutil.copy2(task / "environment" / "input.json", app / "input.json")
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


def test_verifier_execution_does_not_mutate_task_bundles(tmp_path: Path) -> None:
    before = _task_tree_snapshot()

    result = _run_verifier(*_prepare_case(tmp_path, RATIONAL_TASK, "computed"))

    assert result["correctness"] == 1.0
    assert _task_tree_snapshot() == before


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
            "autoformalization-semantic-audit",
            lambda result: result["operator_mismatch_certificate"].update(
                dot_product=1
            ),
        ),
        (
            "calendar-good-days-audit",
            lambda result: result.update(count=15),
        ),
        (
            "finite-magma-countermodel",
            lambda result: result["table"][1].__setitem__(1, 2),
        ),
        (
            "matrix-square-zero-counterexample",
            lambda result: result.update(matrix=[[1, 0], [0, 0]]),
        ),
        (
            "metric-tsp-proof-repair",
            lambda result: result["weights"].update(optimal=31),
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
            "well-total-domination-counterexample",
            lambda result: result.update(degree_sum=7),
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


@pytest.mark.parametrize("task_name", VERIFIER_TASKS)
def test_verifiers_reject_unhashable_assurance(
    tmp_path: Path,
    task_name: str,
) -> None:
    task, app, logs = _prepare_case(tmp_path, task_name, "computed")
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["claimed_assurance"] = []
    _write_json(submission_path, submission)

    rejected = _run_verifier(task, app, logs)
    assert rejected["scope_accuracy"] == 0.0
    assert rejected["reward"] == 0.0
    assert rejected["false_certification"] is False


@pytest.mark.parametrize("task_name", VERIFIER_TASKS)
@pytest.mark.parametrize(
    "attack",
    (
        "malformed-output",
        "missing-output",
        "wrong-result",
        "mismatched-claim",
        "incomplete-scope",
        "escaped-evidence",
        "unsupported-verified",
    ),
)
def test_verifiers_fail_closed_on_submission_attacks(
    tmp_path: Path,
    task_name: str,
    attack: str,
) -> None:
    task, app, logs = _prepare_case(tmp_path, task_name, f"attack-{attack}")
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    if attack != "unsupported-verified":
        submission["claimed_assurance"] = "COMPUTED"

    if attack == "malformed-output":
        submission_path.write_text("{", encoding="utf-8")
    elif attack == "missing-output":
        submission_path.unlink()
    elif attack == "wrong-result":
        submission["result"] = {}
        _write_json(submission_path, submission)
    elif attack == "mismatched-claim":
        submission["conclusion"] = "UNSUPPORTED"
        _write_json(submission_path, submission)
    elif attack == "incomplete-scope":
        submission["scope"] = "incomplete"
        _write_json(submission_path, submission)
    elif attack == "escaped-evidence":
        submission["evidence"] = [
            {
                "path": "../answer.txt",
                "sha256": submission["evidence"][0]["sha256"],
            }
        ]
        _write_json(submission_path, submission)
    else:
        _write_json(submission_path, submission)

    rejected = _run_verifier(task, app, logs)
    if attack in {"incomplete-scope", "escaped-evidence"}:
        component = (
            "scope_accuracy" if attack == "incomplete-scope" else "evidence_validity"
        )
        assert rejected[component] == 0.0
        assert rejected["reward"] < 1.0
    else:
        assert rejected["reward"] == 0.0
    if attack == "unsupported-verified":
        assert rejected["false_certification"] is True


def test_polynomial_verifier_rejects_non_array_witness_fields(
    tmp_path: Path,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path,
        "polynomial-tail-counterexample",
        "computed",
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"] = {
        "p_coefficients": {"2": None, "8/3": None, "2/3": None, "0": None},
        "q_coefficients": {"1": None, "199": None, "9900": None},
        "p_roots": {"-1": None, "-1/3": None, "0": None},
        "q_roots": {"-100": None, "-99": None},
        "x1": "0",
        "x2": "1/100",
    }
    _write_json(submission_path, submission)

    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_metric_tsp_repair_accepts_reversed_optimal_tour(tmp_path: Path) -> None:
    task, app, logs = _prepare_case(
        tmp_path,
        "metric-tsp-proof-repair",
        "computed",
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["optimal_tour"] = ["A", "D", "C", "F", "E", "B", "A"]
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)

    accepted = _run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_finite_magma_accepts_alternate_smallest_countermodel(
    tmp_path: Path,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path,
        "finite-magma-countermodel",
        "computed",
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["table"] = [[1, 0], [1, 0]]
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)

    accepted = _run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_total_domination_accepts_reordered_exact_witnesses(
    tmp_path: Path,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path,
        "well-total-domination-counterexample",
        "computed",
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["pendant_vertices"] = ["4", "0"]
    submission["result"]["minimal_total_dominating_sets"] = [
        ["4", "3", "1", "0"],
        ["3", "2", "1"],
    ]
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)

    accepted = _run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_autoformalization_audit_accepts_alternative_exact_witnesses(
    tmp_path: Path,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path,
        "autoformalization-semantic-audit",
        "computed",
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["missing_premise_certificate"] = {
        "dimension": 1,
        "x": [-7],
        "forced_y": [0],
    }
    submission["result"]["operator_mismatch_certificate"] = {
        "dimension": 2,
        "x": [3, -2],
        "y": [2, 3],
        "dot_product": 0,
        "coordinate_products": [6, -6],
    }
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)

    accepted = _run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_autoformalization_audit_rejects_incomplete_defect_set(
    tmp_path: Path,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path,
        "autoformalization-semantic-audit",
        "computed",
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["defects"] = ["MISSING_DIMENSION_PREMISE"]
    _write_json(submission_path, submission)

    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


@pytest.mark.parametrize(
    "task_name",
    [
        "autoformalization-semantic-audit",
        "divisibility-construction-witness",
        "finite-magma-countermodel",
        "metric-tsp-proof-repair",
        "natural-subtraction-proof-repair",
        "well-total-domination-counterexample",
    ],
)
def test_verifiers_reject_replaced_workspace_inputs(
    tmp_path: Path,
    task_name: str,
) -> None:
    task, app, logs = _prepare_case(tmp_path, task_name, "computed")
    input_path = app / "input.json"
    input_data = json.loads(input_path.read_text())
    input_data["task_id"] = "tampered"
    _write_json(input_path, input_data)

    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


@pytest.mark.parametrize(
    "task_name",
    [
        "autoformalization-semantic-audit",
        "divisibility-construction-witness",
        "finite-magma-countermodel",
        "metric-tsp-proof-repair",
        "modular-cubic-obstruction",
        "natural-subtraction-proof-repair",
        "well-total-domination-counterexample",
    ],
)
def test_hardening_targets_accept_reference_solutions(
    tmp_path: Path,
    task_name: str,
) -> None:
    result = _run_verifier(*_prepare_case(tmp_path, task_name, "computed"))
    assert result["correctness"] == 1.0
    assert result["reward"] == pytest.approx(1.0)


def test_symbolic_block_decomposition_accepts_alternative_sum_zero_basis(
    tmp_path: Path,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path, "symbolic-block-determinant-decomposition", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["basis_change"] = [
        ["1", "1", "0"],
        ["1", "-1", "1"],
        ["1", "0", "-1"],
    ]
    submission["result"]["basis_change_inverse"] = [
        ["1/3", "1/3", "1/3"],
        ["2/3", "-1/3", "-1/3"],
        ["1/3", "1/3", "-2/3"],
    ]
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)

    accepted = _run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_parameterized_sharp_bound_accepts_permuted_certificates(
    tmp_path: Path,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path, "parameterized-sharp-bound-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    result = submission["result"]
    result["certificate"]["tangent_variables"] = ["c", "a", "b"]
    result["certificate"]["schur_ordering"] = ["b", "c", "a"]
    result["boundary_family"] = {
        "vanishing_variable": "a",
        "other_variables": ["c", "b"],
        "parameter": "t->0+",
        "limit": "1/4",
        "attained_for_positive_parameter": False,
    }
    result["audit"]["defects"].reverse()
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)

    accepted = _run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("transition", {"numerator": 4, "denominator": 1}),
        (
            "high_regime",
            {
                "condition": "d>=15/4",
                "bound": "1/4",
                "remainder_coefficient": "d-15/4",
                "attainment": "ATTAINED_FOR_ALL_D",
            },
        ),
        (
            "boundary_family",
            {
                "vanishing_variable": "c",
                "other_variables": ["a", "b"],
                "parameter": "t->0+",
                "limit": "1/4",
                "attained_for_positive_parameter": True,
            },
        ),
    ],
)
def test_parameterized_sharp_bound_rejects_corrupted_sharpness(
    tmp_path: Path,
    field: str,
    replacement: object,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path, "parameterized-sharp-bound-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"][field] = replacement
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)

    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("basis_change_inverse", [["1", "0", "0"], ["0", "1", "0"], ["0", "0", "1"]]),
        ("channels", ["A-B", "A+2B", "A-B"]),
        ("basis_change", [["1", "1", "1"], ["1", "-1", "0"], ["0", "0", "-1"]]),
    ],
)
def test_symbolic_block_decomposition_rejects_corrupted_certificates(
    tmp_path: Path,
    field: str,
    replacement: object,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path, "symbolic-block-determinant-decomposition", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"][field] = replacement
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)

    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_metric_tsp_scope_is_part_of_correctness(tmp_path: Path) -> None:
    task, app, logs = _prepare_case(tmp_path, "metric-tsp-proof-repair", "computed")
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["scope"] = "wrong scope"
    _write_json(submission_path, submission)

    rejected = _run_verifier(task, app, logs)
    assert rejected["scope_accuracy"] == 0.0
    assert rejected["reward"] == 0.0


def test_metric_tsp_evidence_requires_calculations(tmp_path: Path) -> None:
    task, app, logs = _prepare_case(tmp_path, "metric-tsp-proof-repair", "computed")
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    evidence_path = app / "evidence" / "answer.txt"
    evidence_path.write_text(
        "MST Euler shortcut optimal approximation\nRESULT_JSON: {}\n"
    )
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)

    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["evidence_validity"] == 0.0
    assert rejected["reward"] == pytest.approx(0.9)


def test_metric_tsp_accepts_factor_two_claim(tmp_path: Path) -> None:
    task, app, logs = _prepare_case(tmp_path, "metric-tsp-proof-repair", "computed")
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["corrected_claim"] = "factor-2 approximation"
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)

    accepted = _run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0


def test_divisibility_accepts_schema_valid_integral_numbers(tmp_path: Path) -> None:
    task, app, logs = _prepare_case(
        tmp_path, "divisibility-construction-witness", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"] = {
        key: float(value) for key, value in submission["result"].items()
    }
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)

    accepted = _run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0


def test_modular_obstruction_requires_the_certified_modulus(tmp_path: Path) -> None:
    task, app, logs = _prepare_case(tmp_path, "modular-cubic-obstruction", "computed")
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["modulus"] = 14
    _write_json(submission_path, submission)

    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_natural_subtraction_schema_requires_both_basis_entries() -> None:
    task = _task("natural-subtraction-proof-repair")
    schema = json.loads((task / "environment" / "submission_schema.json").read_text())
    submission = json.loads((task / "solution" / "submission.json").read_text())
    submission["result"]["basis_order"] = []
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(submission)

    submission = json.loads((task / "solution" / "submission.json").read_text())
    submission["result"]["multipliers"] = ["1"]
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(submission)


def test_autoformalization_rejects_positive_lean_compile_claim(
    tmp_path: Path,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path, "autoformalization-semantic-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    evidence_path = app / "evidence" / "answer.txt"
    evidence_path.write_text(
        "dimension dot product coordinate\n"
        "Both Lean declarations compile.\n"
        "RESULT_JSON: {}\n"
    )
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)

    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["evidence_validity"] == 0.0
    assert rejected["reward"] == pytest.approx(0.9)


def test_inverse_distance_audit_accepts_alternative_rational_direction(
    tmp_path: Path,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path, "inverse-distance-remainder-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["directional_witnesses"][0] = {
        "direction": [
            {"numerator": 4, "denominator": 5},
            {"numerator": 3, "denominator": 5},
        ],
        "quadratic_coefficient": {"numerator": 23, "denominator": 50},
        "sign": "POSITIVE",
        "normalized_residual_limit": "quadratic_coefficient",
    }
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)

    accepted = _run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (
            ("second_order_term", "dot_square_coefficient"),
            {"numerator": 1, "denominator": 1},
        ),
        (
            ("directional_witnesses", 0, "quadratic_coefficient"),
            {"numerator": 2, "denominator": 1},
        ),
        (
            ("response_audit", "defects"),
            ["CUBIC_REMAINDER_FALSE"],
        ),
    ],
)
def test_inverse_distance_audit_rejects_corrupted_certificates(
    tmp_path: Path,
    path: tuple[object, ...],
    replacement: object,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path, "inverse-distance-remainder-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    target = submission["result"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)

    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_generated_lemma_audit_enforces_visible_divisor_witness_bounds(
    tmp_path: Path,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path, "generated-lemma-vacuity-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    audit = submission["result"]["common_divisor_audit"]
    audit["a"] = 1_000_001
    audit["b"] = 1_000_002
    audit["dividends"] = [
        4 * audit["a"] * audit["b"] - 1,
        2 * audit["a"] - 1,
        2 * audit["a"] + 1,
    ]
    audit["original_premise_holds"] = False
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)
    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0


def test_noncompact_lefschetz_accepts_equivalent_rational_and_cohomology_forms(
    tmp_path: Path,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path, "noncompact-lefschetz-proof-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    counterexample = submission["result"]["counterexample"]
    counterexample["translation"] = {"numerator": 2, "denominator": 2}
    counterexample["compact_support_cohomology"].reverse()
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)
    accepted = _run_verifier(task, app, logs)
    assert accepted["reward"] == pytest.approx(1.0)


@pytest.mark.parametrize("field", ["top_degree_action", "lefschetz_number"])
def test_noncompact_lefschetz_rejects_boolean_in_integer_fields(
    tmp_path: Path, field: str
) -> None:
    task, app, logs = _prepare_case(
        tmp_path, "noncompact-lefschetz-proof-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["counterexample"][field] = True
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)
    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0


def test_noncompact_lefschetz_enforces_visible_translation_bounds(
    tmp_path: Path,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path, "noncompact-lefschetz-proof-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["counterexample"]["translation"] = {
        "numerator": 1_000_001,
        "denominator": 1,
    }
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)
    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0


def test_symbolic_block_certificate_enforces_common_channel_first(
    tmp_path: Path,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path, "symbolic-block-determinant-decomposition", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    result = submission["result"]
    for row in result["basis_change"]:
        row[0], row[1] = row[1], row[0]
    result["basis_change_inverse"][0], result["basis_change_inverse"][1] = (
        result["basis_change_inverse"][1],
        result["basis_change_inverse"][0],
    )
    result["channels"] = ["A-B", "A+2B", "A-B"]
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)
    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0


def test_parameterized_bound_evidence_binds_boundary_family(
    tmp_path: Path,
) -> None:
    task, app, logs = _prepare_case(
        tmp_path, "parameterized-sharp-bound-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["boundary_family"]["vanishing_variable"] = "a"
    submission["result"]["boundary_family"]["other_variables"] = ["b", "c"]
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)
    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["evidence_validity"] == 0.0


def test_inverse_distance_enforces_visible_rational_bounds(tmp_path: Path) -> None:
    task, app, logs = _prepare_case(
        tmp_path, "inverse-distance-remainder-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    coefficient = submission["result"]["directional_witnesses"][0][
        "quadratic_coefficient"
    ]
    coefficient["numerator"] *= 1_000_001
    coefficient["denominator"] *= 1_000_001
    _bind_result_evidence(app, submission)
    _write_json(submission_path, submission)
    rejected = _run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
