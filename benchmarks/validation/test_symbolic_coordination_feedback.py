from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from benchmarks.tooling import symbolic_coordination_codex as codex
from benchmarks.tooling import symbolic_coordination_feedback as feedback
from jsonschema import Draft202012Validator


def _task(tmp_path: Path) -> codex.TaskContract:
    return codex.TaskContract(
        task_id="symbolic-coordination-near-miss-01",
        path=tmp_path,
        harbor_digest="1" * 64,
        public_hashes={},
        verifier_hashes={},
    )


def _verifier(**overrides: object) -> dict[str, object]:
    reward: dict[str, object] = {
        "correctness": 1.0,
        "evidence_validity": 1.0,
        "scope_accuracy": 1.0,
        "assurance_calibration": 1.0,
        "input_binding": 0.0,
        "artifact_binding": 1.0,
        "protocol_compliance": 1.0,
        "false_certification": False,
        "reward": 0.0,
    }
    reward.update(overrides)
    return {
        "execution_status": "COMPLETED",
        "mathematical_observation": "REJECTED",
        "reward": reward,
        "verifier_workspace_outside_model_workspace": True,
    }


def _build(tmp_path: Path) -> feedback.VerifierFeedback:
    return feedback.build_feedback(
        task=_task(tmp_path),
        snapshot_id="sha256:" + "2" * 64,
        initial_submission_digest="sha256:" + "3" * 64,
        verifier_result=_verifier(),
    )


def test_feedback_schema_is_closed_and_current(tmp_path: Path) -> None:
    schema = feedback.VerifierFeedback.model_json_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(_build(tmp_path).model_dump(mode="json"))
    assert schema["additionalProperties"] is False


def test_feedback_exposes_only_allowlisted_typed_diagnostics(tmp_path: Path) -> None:
    value = _build(tmp_path)
    assert value.observation == "REJECTED"
    assert [item.model_dump() for item in value.diagnostics] == [
        {"code": "REPAIR_INPUT_BINDING", "dimension": "INPUT_BINDING"}
    ]
    raw = json.dumps(value.model_dump(mode="json")).lower()
    for secret in ("oracle", "solution", "verifier.py", "expected_coeff", "/app/"):
        assert secret not in raw


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda item: item.update({"unknown": True}), "closed schema"),
        (
            lambda item: item["diagnostics"].append(
                {"code": "EXPECTED_COEFFICIENTS", "dimension": "INPUT_BINDING"}
            ),
            "closed schema",
        ),
        (
            lambda item: item.update({"certainty": "VERIFIED"}),
            "closed schema",
        ),
        (
            lambda item: item["binding"].update(
                {"task_id": "symbolic-coordination-valid-inverse-01"}
            ),
            "stale, substituted",
        ),
        (
            lambda item: item["binding"].update(
                {"verifier_result_digest": "sha256:" + "9" * 64}
            ),
            "stale, substituted",
        ),
    ],
)
def test_feedback_rejects_malformed_stale_substituted_or_overcertain_values(
    tmp_path: Path, mutation: object, message: str
) -> None:
    raw = copy.deepcopy(_build(tmp_path).model_dump(mode="json"))
    mutation(raw)  # type: ignore[operator]
    with pytest.raises(feedback.FeedbackContractError, match=message):
        feedback.validate_feedback(
            raw,
            task=_task(tmp_path),
            snapshot_id="sha256:" + "2" * 64,
            initial_submission_digest="sha256:" + "3" * 64,
            verifier_result=_verifier(),
        )


def test_feedback_rejects_hidden_leakage_key(tmp_path: Path) -> None:
    raw = _build(tmp_path).model_dump(mode="json")
    raw["replacement_answer"] = {"coefficients": [1, 2, 3]}
    with pytest.raises(feedback.FeedbackContractError, match="closed schema"):
        feedback.validate_feedback(
            raw,
            task=_task(tmp_path),
            snapshot_id="sha256:" + "2" * 64,
            initial_submission_digest="sha256:" + "3" * 64,
            verifier_result=_verifier(),
        )


def test_feedback_report_rejects_absence_and_unbound_codes(tmp_path: Path) -> None:
    value = _build(tmp_path)
    missing = tmp_path / "missing.json"
    with pytest.raises(feedback.FeedbackContractError, match="absent or malformed"):
        feedback.validate_feedback_report(
            missing, feedback=value, revision_applied=False
        )
    report = {
        "feedback_report_schema_version": "1",
        "feedback_id": value.feedback_id,
        "task_id": value.binding.task_id,
        "initial_submission_digest": value.binding.initial_submission_digest,
        "status": "UNCHANGED",
        "revision_applied": False,
        "addressed_codes": ["REPAIR_SCOPE"],
    }
    missing.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(feedback.FeedbackContractError, match="unbound or overclaims"):
        feedback.validate_feedback_report(
            missing, feedback=value, revision_applied=False
        )


def test_rejected_result_without_safe_dimension_fails_closed(tmp_path: Path) -> None:
    verifier = _verifier(input_binding=1.0)
    with pytest.raises(feedback.FeedbackContractError, match="no safe diagnostic"):
        feedback.build_feedback(
            task=_task(tmp_path),
            snapshot_id="sha256:" + "2" * 64,
            initial_submission_digest="sha256:" + "3" * 64,
            verifier_result=verifier,
        )
