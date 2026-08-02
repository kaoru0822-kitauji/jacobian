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


def test_research_status_audit_accepts_equivalent_case_order(tmp_path: Path) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "research-status-evidence-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["cases"].reverse()
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)

    accepted = support._run_verifier(task, app, logs)
    assert accepted["correctness"] == 1.0
    assert accepted["reward"] == pytest.approx(1.0)


def test_research_status_audit_rejects_wrong_scope_without_base_reward(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "research-status-evidence-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["scope"] = "wrong scope"
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["scope_accuracy"] == 0.0
    assert rejected["reward"] == pytest.approx(0.2)


def test_research_status_audit_rejects_escaped_evidence_without_base_reward(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "research-status-evidence-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["evidence"] = [
        {
            "path": "../answer.txt",
            "sha256": submission["evidence"][0]["sha256"],
        }
    ]
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["evidence_validity"] == 0.0
    assert rejected["reward"] == pytest.approx(0.2)


def test_research_status_audit_rejects_wrong_assurance_without_base_reward(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "research-status-evidence-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["claimed_assurance"] = "UNVERIFIED"
    support._write_json(submission_path, submission)

    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["assurance_calibration"] == 0.0
    assert rejected["reward"] == pytest.approx(0.2)


def test_research_status_audit_rejects_tampered_frozen_input(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "research-status-evidence-audit", "computed"
    )
    (app / "input.json").write_text('{"cases":[]}')
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_research_status_audit_rejects_extra_selected_citations(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "research-status-evidence-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    for case in submission["result"]["cases"]:
        if case["case_id"] == "binomial-equation-resolution":
            case["selected_evidence_ids"].append("SW1999")
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_research_status_audit_rejects_undeclared_result_field(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "research-status-evidence-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["current_status"] = "ALL_FOUR_PROBLEMS_RESOLVED"
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_research_status_audit_rejects_non_string_case_id(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "research-status-evidence-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["result"]["cases"][0]["case_id"] = ["workshop-equation-status"]
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_research_status_audit_rejects_evidence_without_result_marker(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "research-status-evidence-audit", "computed"
    )
    evidence_path = app / "evidence" / "answer.txt"
    submission = json.loads((app / "submission.json").read_text())
    evidence_path.write_text(
        "The frozen packets separate direct resolution evidence, "
        "partial-progress evidence, historical openness, and a bare "
        "problem listing. A negative web search or an old open-problem "
        "citation cannot establish present status.\n"
    )
    submission["evidence"][0]["sha256"] = support._digest(evidence_path)
    support._write_json(app / "submission.json", submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["evidence_validity"] == 0.0
    assert rejected["reward"] == pytest.approx(0.2)


def test_research_status_audit_rejects_oversized_evidence(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "research-status-evidence-audit", "computed"
    )
    evidence_path = app / "evidence" / "answer.txt"
    submission = json.loads((app / "submission.json").read_text())
    evidence_path.write_text("x" * 2_097_152)
    submission["evidence"][0]["sha256"] = support._digest(evidence_path)
    support._write_json(app / "submission.json", submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["evidence_validity"] == 0.0


def test_research_status_audit_oversized_evidence_does_not_block_reward_record(
    tmp_path: Path,
) -> None:
    """The evidence byte bound fires before the digest-bound resolution hashes
    the file, so an oversized malformed artifact yields a complete reward.json
    (math still correct, evidence rejected) instead of a verifier timeout.
    """
    task, app, logs = support._prepare_case(
        tmp_path, "research-status-evidence-audit", "computed"
    )
    evidence_path = app / "evidence" / "answer.txt"
    submission = json.loads((app / "submission.json").read_text())
    evidence_path.write_text("x" * 2_097_152)
    # A deliberately wrong digest proves the size gate, not the hash, rejects.
    submission["evidence"][0]["sha256"] = "sha256:" + "0" * 64
    support._write_json(app / "submission.json", submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 1.0
    assert rejected["evidence_validity"] == 0.0
    assert rejected["reward"] == pytest.approx(0.2)


def test_research_status_audit_rejects_deeply_nested_submission(
    tmp_path: Path,
) -> None:
    """A deeply nested JSON payload overflows the CPython recursion limit; the
    verifier treats it as a malformed submission and writes reward.json with
    zero reward instead of crashing without a record.
    """
    task, app, logs = support._prepare_case(
        tmp_path, "research-status-evidence-audit", "computed"
    )
    (app / "submission.json").write_text("[" * 12000 + "1" + "]" * 12000)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


def test_research_status_audit_rejects_checked_assurance_above_ceiling(
    tmp_path: Path,
) -> None:
    """CHECKED is above the task's COMPUTED assurance ceiling, so it is an
    unsupported certification for this task and forces reward to zero rather
    than granting the partial reward a below-ceiling mismatch would earn.
    """
    task, app, logs = support._prepare_case(
        tmp_path, "research-status-evidence-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    submission["claimed_assurance"] = "CHECKED"
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["reward"] == 0.0


def test_research_status_audit_rejects_invalid_utf8_evidence(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "research-status-evidence-audit", "computed"
    )
    evidence_path = app / "evidence" / "answer.txt"
    submission = json.loads((app / "submission.json").read_text())
    evidence_path.write_bytes(
        b"\xff\xfe resolution partial-progress historical problem listing"
    )
    submission["evidence"][0]["sha256"] = support._digest(evidence_path)
    support._write_json(app / "submission.json", submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["evidence_validity"] == 0.0


def test_research_status_audit_requires_exponent_range_inference(
    tmp_path: Path,
) -> None:
    task, app, logs = support._prepare_case(
        tmp_path, "research-status-evidence-audit", "computed"
    )
    submission_path = app / "submission.json"
    submission = json.loads(submission_path.read_text())
    for case in submission["result"]["cases"]:
        if case["case_id"] == "lebesgue-nagell-progress":
            case["unsupported_inferences"] = []
    support._bind_result_evidence(app, submission)
    support._write_json(submission_path, submission)
    rejected = support._run_verifier(task, app, logs)
    assert rejected["correctness"] == 0.0
    assert rejected["reward"] == 0.0


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
