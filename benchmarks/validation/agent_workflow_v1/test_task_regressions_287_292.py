from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.validation.agent_workflow_v1 import support
from jsonschema import Draft202012Validator


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("valuation_induction", "sub_one_term_lower_bounds", 1), [1, 2]),
        (("target_transfer", "b_difference"), [2, 3]),
        (("finite_testing_role",), "FINITE_CASES_PROVE_ALL_K"),
    ],
)
def test_putnam_2adic_audit_rejects_corrupted_induction_certificates(
    tmp_path: Path,
    path: tuple[object, ...],
    replacement: object,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "putnam-2adic-induction-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    target = submission["result"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_generated_lemma_audit_enforces_visible_divisor_witness_bounds(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
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
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0


def test_noncompact_lefschetz_accepts_equivalent_rational_and_cohomology_forms(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "noncompact-lefschetz-proof-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    counterexample = submission["result"]["counterexample"]
    counterexample["translation"] = {"numerator": 2, "denominator": 2}
    counterexample["compact_support_cohomology"].reverse()
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)
    accepted = support._run_verifier(task, app, logs)
    assert accepted["reward"] == pytest.approx(1.0)


@pytest.mark.parametrize("field", ["top_degree_action", "lefschetz_number"])
def test_noncompact_lefschetz_rejects_boolean_in_integer_fields(
    tmp_path: Path, field: str
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "noncompact-lefschetz-proof-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["counterexample"][field] = True
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0


def test_noncompact_lefschetz_enforces_visible_translation_bounds(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "noncompact-lefschetz-proof-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["counterexample"]["translation"] = {
        "numerator": 1_000_001,
        "denominator": 1,
    }
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0


def test_symbolic_block_certificate_enforces_common_channel_first(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
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
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0


def test_parameterized_bound_evidence_binds_boundary_family(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "parameterized-sharp-bound-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["boundary_family"]["vanishing_variable"] = "a"
    submission["result"]["boundary_family"]["other_variables"] = ["b", "c"]
    support._bind_result_evidence(app, submission)
    evidence_path = app / "evidence" / "answer.txt"
    text = evidence_path.read_text().replace(
        'BOUNDARY_FAMILY_JSON: {"attained_for_positive_parameter":false,"limit":"1/4","other_variables":["b","c"],"parameter":"t->0+","vanishing_variable":"a"}',
        'BOUNDARY_FAMILY_JSON: {"attained_for_positive_parameter":false,"limit":"1/4","other_variables":["a","b"],"parameter":"t->0+","vanishing_variable":"c"}',
    )
    evidence_path.write_text(text)
    submission["evidence"][0]["sha256"] = support._digest(evidence_path)
    support._write_json(submission_path, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["evidence_validity"] == 0.0


def test_inverse_distance_enforces_visible_rational_bounds(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "inverse-distance-remainder-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    coefficient = submission["result"]["directional_witnesses"][0][
        "quadratic_coefficient"
    ]
    coefficient["numerator"] *= 1_000_001
    coefficient["denominator"] *= 1_000_001
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0


def test_complex_elimination_does_not_require_prescribed_recurrence(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "complex-power-sum-elimination", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"].pop("recurrence")
    submission["result"]["elimination"].pop("hypothesis_factorization")
    schema = json.loads((task / "environment" / "submission_schema.json").read_text())
    Draft202012Validator(schema).validate(submission)
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)
