import importlib.util
import json
import sys
from pathlib import Path

from benchmarks.validation.agent_workflow_v1 import support

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT / "benchmarks/datasets/agent-workflow-v1/pythagorean-generator-recurrence"
TASK_NAME = "pythagorean-generator-recurrence"


def load_verifier():
    sys.path.insert(0, str(TASK / "tests"))
    spec = importlib.util.spec_from_file_location(
        "pythagorean_recurrence_verifier", TASK / "tests/verifier.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def candidate(seed=(2, 1)):
    verifier = load_verifier()
    m, n = seed
    stages = []
    for index in range(8):
        stages.append(verifier.expected_stage(index, m, n))
        m, n = 2 * m + n, m
    return {
        "transform_matrix": [[2, 1], [1, 0]],
        "transform_determinant": -1,
        "invariant_multiplier": -1,
        "stages": stages,
    }


def _case(tmp_path: Path):
    return support._prepare_case(tmp_path, TASK_NAME, "computed")


def _rewrite(app: Path, submission: dict) -> None:
    support._bind_result_evidence(app, submission)
    support._write_json(app / "submission.json", submission)


def test_accepts_two_distinct_valid_seeds():
    verifier = load_verifier()
    assert verifier.valid_result(candidate((2, 1)))
    assert verifier.valid_result(candidate((5, 2)))


def test_corrupt_stage_and_transform_are_rejected():
    verifier = load_verifier()
    bad = candidate()
    bad["stages"][4]["c"] += 1
    assert not verifier.valid_result(bad)
    bad = candidate()
    bad["transform_matrix"] = [[1, 2], [0, 1]]
    assert not verifier.valid_result(bad)


def test_nonprimitive_or_same_parity_seed_is_rejected():
    verifier = load_verifier()
    assert not verifier.valid_result(candidate((6, 3)))
    assert not verifier.valid_result(candidate((3, 1)))


def test_contract_has_computed_ceiling():
    schema = json.loads((TASK / "environment/submission_schema.json").read_text())
    assert schema["properties"]["claimed_assurance"] == {"const": "COMPUTED"}


def test_booleans_rejected_in_integer_fields():
    verifier = load_verifier()
    bad = candidate()
    bad["transform_determinant"] = True
    assert not verifier.valid_result(bad)
    bad = candidate()
    bad["invariant_multiplier"] = True
    assert not verifier.valid_result(bad)
    bad = candidate()
    bad["transform_matrix"] = [[2, True], [1, 0]]
    assert not verifier.valid_result(bad)
    bad = candidate()
    bad["stages"][0]["gcd"] = True
    assert not verifier.valid_result(bad)
    bad = candidate()
    bad["stages"][0]["q"] = True
    assert not verifier.valid_result(bad)
    bad = candidate()
    bad["stages"][0]["stage"] = False
    assert not verifier.valid_result(bad)


def test_integer_rejected_in_boolean_field():
    verifier = load_verifier()
    bad = candidate()
    bad["stages"][0]["parity_opposite"] = 1
    assert not verifier.valid_result(bad)


def test_reference_passes(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    result = support._run_verifier(task, app, logs)
    assert result["protocol_compliance"] == 1.0
    assert result["reward"] == 1.0


def test_false_verified_is_rejected(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    submission["claimed_assurance"] = "VERIFIED"
    support._write_json(app / "submission.json", submission)
    result = support._run_verifier(task, app, logs)
    assert result["reward"] == 0.0
    assert result["false_certification"] is True


def test_protocol_failure_preserves_math_correctness(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    submission["claimed_assurance"] = "VERIFIED"
    support._write_json(app / "submission.json", submission)
    result = support._run_verifier(task, app, logs)
    assert result["protocol_compliance"] == 0.0
    assert result["correctness"] == 1.0
    assert result["reward"] == 0.0


def test_unverified_claim_preserves_other_metrics(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    submission["claimed_assurance"] = "UNVERIFIED"
    support._write_json(app / "submission.json", submission)
    result = support._run_verifier(task, app, logs)
    assert result["correctness"] == 1.0
    assert result["evidence_validity"] == 1.0
    assert result["scope_accuracy"] == 1.0
    assert result["assurance_calibration"] == 0.0
    assert result["reward"] == 0.0


def test_assurance_calibration_independent_of_envelope(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    submission["extra_field"] = True
    support._write_json(app / "submission.json", submission)
    result = support._run_verifier(task, app, logs)
    assert result["assurance_calibration"] == 1.0
    assert result["reward"] == 0.0


def test_oversized_evidence_is_rejected_without_crashing(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    (app / "evidence" / "answer.txt").write_text(
        "recurrence coprime pythagorean " + "x" * 65536
    )
    submission["evidence"][0]["sha256"] = support._digest(
        app / "evidence" / "answer.txt"
    )
    support._write_json(app / "submission.json", submission)
    result = support._run_verifier(task, app, logs)
    assert result["evidence_validity"] == 0.0
    assert result["reward"] == 0.0


def test_keyword_only_evidence_without_result_binding_is_rejected(
    tmp_path: Path,
) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    evidence = app / "evidence" / "answer.txt"
    evidence.write_text("recurrence coprime pythagorean\n")
    submission["evidence"][0]["sha256"] = support._digest(evidence)
    support._write_json(app / "submission.json", submission)
    result = support._run_verifier(task, app, logs)
    assert result["evidence_validity"] == 0.0
    assert result["reward"] == 0.0


def test_evidence_with_wrong_result_json_is_rejected(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    evidence = app / "evidence" / "answer.txt"
    wrong = json.loads(json.dumps(submission["result"]))
    wrong["transform_determinant"] = 1
    evidence.write_text(
        "recurrence coprime pythagorean\n"
        "RESULT_JSON:" + json.dumps(wrong, sort_keys=True, separators=(",", ":")) + "\n"
    )
    submission["evidence"][0]["sha256"] = support._digest(evidence)
    support._write_json(app / "submission.json", submission)
    result = support._run_verifier(task, app, logs)
    assert result["evidence_validity"] == 0.0
    assert result["reward"] == 0.0


def test_boolean_in_result_json_evidence_is_rejected(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    evidence = app / "evidence" / "answer.txt"
    coerced = json.loads(json.dumps(submission["result"]))
    coerced["stages"][0]["gcd"] = True
    assert coerced == submission["result"]  # Python coerces True == 1
    evidence.write_text(
        "recurrence coprime pythagorean\n"
        "RESULT_JSON:"
        + json.dumps(coerced, sort_keys=True, separators=(",", ":"))
        + "\n"
    )
    submission["evidence"][0]["sha256"] = support._digest(evidence)
    support._write_json(app / "submission.json", submission)
    result = support._run_verifier(task, app, logs)
    assert result["evidence_validity"] == 0.0


def test_symlinked_workspace_input_is_rejected(tmp_path: Path) -> None:
    task, app, logs = _case(tmp_path)
    original = app / "input-original.json"
    (app / "input.json").rename(original)
    (app / "input.json").symlink_to(original)
    assert support._run_verifier(task, app, logs)["reward"] == 0.0


def test_input_tamper_preserves_assurance_diagnostics(tmp_path: Path) -> None:
    """When the workspace input is altered, mathematical acceptance is
    gated to zero but assurance/scope/evidence diagnostics remain
    independently evaluated rather than collapsing to zero."""
    task, app, logs = _case(tmp_path)
    (app / "input.json").write_text("{}")
    result = support._run_verifier(task, app, logs)
    assert result["correctness"] == 0.0
    assert result["evidence_validity"] == 0.0
    assert result["scope_accuracy"] == 1.0
    assert result["assurance_calibration"] == 1.0
    assert result["reward"] == 0.0


def test_result_shape_violation_reports_protocol_failure(tmp_path: Path) -> None:
    """A schema-invalid result (extra property) must report
    protocol_compliance = 0, not just correctness = 0."""
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    submission["result"]["extra_property"] = 1
    support._write_json(app / "submission.json", submission)
    result = support._run_verifier(task, app, logs)
    assert result["protocol_compliance"] == 0.0
    assert result["correctness"] == 0.0
    assert result["reward"] == 0.0


def test_float_in_result_reports_protocol_failure(tmp_path: Path) -> None:
    """A float where an integer is required is a schema violation that
    must be reported as protocol_compliance = 0."""
    task, app, logs = _case(tmp_path)
    submission = json.loads((app / "submission.json").read_text())
    submission["result"]["transform_determinant"] = -1.0
    support._write_json(app / "submission.json", submission)
    result = support._run_verifier(task, app, logs)
    assert result["protocol_compliance"] == 0.0
    assert result["correctness"] == 0.0
    assert result["reward"] == 0.0


def test_instruction_documents_evidence_binding():
    text = (TASK / "instruction.md").read_text().casefold()
    assert "result_json" in text
    assert "64 kib" in text
