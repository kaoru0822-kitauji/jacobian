from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.validation.agent_workflow_v1 import support
from jsonschema import Draft202012Validator, ValidationError


def test_metric_tsp_scope_is_part_of_correctness(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "metric-tsp-proof-repair", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["scope"] = "wrong scope"
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["scope_accuracy"] == 0.0
    assert rejected["reward"] == 0.0


def test_metric_tsp_evidence_requires_calculations(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "metric-tsp-proof-repair", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    evidence_path = app / "evidence" / "answer.txt"
    evidence_path.write_text(
        "MST Euler shortcut optimal approximation\nRESULT_JSON: {}\n"
    )
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["evidence_validity"] == 0.0
    assert rejected["reward"] == pytest.approx(0.9)


def test_metric_tsp_accepts_factor_two_claim(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "metric-tsp-proof-repair", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["corrected_claim"] = "factor-2 approximation"
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0


def test_divisibility_accepts_schema_valid_integral_numbers(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "divisibility-construction-witness", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"] = {
        key: float(value) for key, value in submission["result"].items()
    }
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0


def test_modular_obstruction_requires_the_certified_modulus(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "modular-cubic-obstruction", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["modulus"] = 14
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_natural_subtraction_schema_requires_both_basis_entries() -> None:
    task = support._task("natural-subtraction-proof-repair")
    schema = json.loads((task / "environment" / "submission_schema.json").read_text())
    submission = json.loads((task / "solution" / "submission.json").read_text())
    submission["result"]["basis_order"] = []
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(submission)

    submission = json.loads((task / "solution" / "submission.json").read_text())
    submission["result"]["multipliers"] = ["1"]
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(submission)


def test_complex_power_sum_accepts_reversed_branch_order(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "complex-power-sum-elimination", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["branches"].reverse()
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (
            ("recurrence", "power_sums", "5", 3),
            {"numerator": 19, "denominator": 1},
        ),
        (
            ("branches", 0, "target", "sqrt17"),
            {"numerator": 3, "denominator": 1},
        ),
        (("branches", 0, "denominator_norms", "s_minus_12"), 31),
        (("branches",), []),
    ],
)
def test_complex_power_sum_rejects_corrupted_certificates(
    tmp_path: Path,
    path: tuple[object, ...],
    replacement: object,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "complex-power-sum-elimination", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    target = submission["result"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_autoformalization_rejects_positive_lean_compile_claim(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
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
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["evidence_validity"] == 0.0
    assert rejected["reward"] == pytest.approx(0.9)


def test_inverse_distance_audit_accepts_alternative_rational_direction(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
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
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
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
    task, app, logs = support._prepare_case(
        tmp_path, "inverse-distance-remainder-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    target = submission["result"]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_indexed_pairwise_vacuity_accepts_canonical_limitation(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )

    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)
    assert accepted["false_certification"] is False


def test_indexed_pairwise_vacuity_rejects_overclaiming_limitations(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["limitations"] = [
        "The verifier fully settles the indexed pairwise vacuity question."
    ]
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["reward"] == 0.0


def test_indexed_pairwise_vacuity_rejects_boolean_witness_elements(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["subgroup"] = [False, 4, 8]
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_indexed_pairwise_vacuity_rejects_boolean_coset_elements(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["cosets"][0][0] = False
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_indexed_pairwise_vacuity_rejects_boolean_artifact_elements(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["part_artifact"]["elements"] = [False, 4, 8]
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_indexed_pairwise_vacuity_rejects_empty_limitations(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["limitations"] = []
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["reward"] == 0.0


def test_indexed_pairwise_vacuity_rejects_broader_scope(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["scope"] = "the underlying conjecture"
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["scope_accuracy"] == 0.0
    assert rejected["reward"] == 0.0


def test_indexed_pairwise_vacuity_rejects_assurance_above_ceiling(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["claimed_assurance"] = "CHECKED"
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["assurance_calibration"] == 0.0
    assert rejected["reward"] == 0.0


def test_indexed_pairwise_vacuity_accepts_assurance_underclaim(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["claimed_assurance"] = "UNVERIFIED"
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["assurance_calibration"] == 0.0
    assert accepted["reward"] == pytest.approx(0.9)


def test_indexed_pairwise_vacuity_accepts_schema_valid_integral_floats(
    tmp_path: Path,
) -> None:
    """JSON Schema's integer type accepts zero-fraction floats (VvCg2)."""
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    result = submission["result"]
    result["modulus"] = float(result["modulus"])
    result["subgroup_step"] = float(result["subgroup_step"])
    result["subgroup"] = [float(value) for value in result["subgroup"]]
    result["representatives"] = [float(value) for value in result["representatives"]]
    result["cosets"] = [[float(value) for value in coset] for coset in result["cosets"]]
    result["part_artifact"]["elements"] = [
        float(value) for value in result["part_artifact"]["elements"]
    ]
    result["covering_part_references"] = [
        float(value) for value in result["covering_part_references"]
    ]
    result["duplicate_indices"] = [
        float(value) for value in result["duplicate_indices"]
    ]
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_indexed_pairwise_vacuity_rejects_non_integral_floats(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["modulus"] = 12.5
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_indexed_pairwise_vacuity_accepts_unordered_subgroup_and_coset_elements(
    tmp_path: Path,
) -> None:
    """The schema requires only unique elements, so element order is free (VvKD8)."""
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    result = submission["result"]
    result["subgroup"] = [8, 0, 4]
    result["cosets"][0] = [8, 4, 0]
    result["part_artifact"]["elements"] = [8, 0, 4]
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_indexed_pairwise_vacuity_accepts_either_duplicate_index_order(
    tmp_path: Path,
) -> None:
    """The schema requires two distinct indices, not ascending order (VvKD9)."""
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["duplicate_indices"] = [1, 0]
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_indexed_pairwise_vacuity_rejects_duplicate_index_pair_out_of_range(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["duplicate_indices"] = [0, 4]
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_indexed_pairwise_vacuity_rejects_affirmative_open_conjecture_claim(
    tmp_path: Path,
) -> None:
    """A limitation that affirms settling the conjecture must fail (VvCgy)."""
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["limitations"] = [
        "The verifier settles the open conjecture with this finite audit."
    ]
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["reward"] == 0.0


def test_indexed_pairwise_vacuity_rejects_limitation_mentioning_only_keywords(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["limitations"] = ["This relates to the open conjecture."]
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["reward"] == 0.0


def test_indexed_pairwise_vacuity_rejects_contradicting_evidence(
    tmp_path: Path,
) -> None:
    """Evidence negating the submitted conclusion must be invalid (VvCgz)."""
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    evidence_path = app / "evidence" / "answer.txt"
    evidence_path.write_text(
        "This is not an exact cover; Set.range is not vacuously true.\n",
        encoding="utf-8",
    )
    submission["evidence"][0]["sha256"] = support._digest(evidence_path)
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["evidence_validity"] == 0.0
    assert rejected["reward"] == pytest.approx(0.9)


def test_indexed_pairwise_vacuity_rejects_duplicated_evidence_descriptors(
    tmp_path: Path,
) -> None:
    """The schema caps evidence at one descriptor (VvCg4)."""
    task, app, logs = support._prepare_case(
        tmp_path, "indexed-pairwise-vacuity", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["evidence"] = [submission["evidence"][0], submission["evidence"][0]]
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["evidence_validity"] == 0.0
    assert rejected["reward"] == pytest.approx(0.9)


def test_agent_workflow_v1_readme_keeps_1_1_0_and_adds_1_2_0_entry() -> None:
    readme = (support.TASKS / "README.md").read_text(encoding="utf-8")

    assert "Version 1.1.0 adds the independently reviewed finite-magma and" in readme
    assert "Version 1.2.0 adds the indexed-pairwise-vacuity audit" in readme
