from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.validation.agent_workflow_v1 import support


def test_polynomial_verifier_rejects_non_array_witness_fields(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
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
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_metric_tsp_repair_accepts_reversed_optimal_tour(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(
        tmp_path,
        "metric-tsp-proof-repair",
        "computed",
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["optimal_tour"] = ["A", "D", "C", "F", "E", "B", "A"]
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_finite_magma_accepts_alternate_smallest_countermodel(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path,
        "finite-magma-countermodel",
        "computed",
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["table"] = [[1, 0], [1, 0]]
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_total_domination_accepts_reordered_exact_witnesses(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
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
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_graph_atlas_enumeration_accepts_reordered_representatives(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path,
        "graph-atlas-enumeration",
        "computed",
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["representatives"].reverse()
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


@pytest.mark.parametrize("mutation", ["missing", "duplicate"])
def test_graph_atlas_enumeration_rejects_incomplete_class_sets(
    tmp_path: Path,
    mutation: str,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path,
        "graph-atlas-enumeration",
        "computed",
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    representatives = submission["result"]["representatives"]
    if mutation == "missing":
        representatives.pop()
        submission["result"]["class_count"] = 7
    else:
        representatives[-1] = representatives[0]
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_autoformalization_audit_accepts_alternative_exact_witnesses(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
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
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_autoformalization_audit_rejects_incomplete_defect_set(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path,
        "autoformalization-semantic-audit",
        "computed",
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["defects"] = ["MISSING_DIMENSION_PREMISE"]
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


@pytest.mark.parametrize(
    "task_name",
    [
        "autoformalization-semantic-audit",
        "complex-power-sum-elimination",
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
    task, app, logs = support._prepare_case(tmp_path, task_name, "computed")
    input_path = app / "input.json"
    input_data = json.loads(input_path.read_text())
    input_data["task_id"] = "tampered"
    support._write_json(input_path, input_data)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


@pytest.mark.parametrize(
    "task_name",
    [
        "autoformalization-semantic-audit",
        "complex-power-sum-elimination",
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
    result = support._run_verifier(
        *support._prepare_case(tmp_path, task_name, "computed")
    )
    assert result["correctness"] == 1.0
    assert result["reward"] == pytest.approx(1.0)


def test_symbolic_block_decomposition_accepts_alternative_sum_zero_basis(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
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
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_parameterized_sharp_bound_accepts_permuted_certificates(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
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
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
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
    task, app, logs = support._prepare_case(
        tmp_path, "parameterized-sharp-bound-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"][field] = replacement
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
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
    task, app, logs = support._prepare_case(
        tmp_path, "symbolic-block-determinant-decomposition", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"][field] = replacement
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0
