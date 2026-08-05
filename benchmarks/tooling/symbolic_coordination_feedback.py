"""One bounded, leakage-safe verifier-feedback round for condition D.

This module deliberately composes the existing host runner without changing
the A/B/C prompts or runtime contract.  The model sees only a closed feedback
object derived from clean-room verifier dimensions; it never sees verifier
output, source, hidden fixtures, or replacement mathematical content.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from benchmarks.tooling import symbolic_coordination_codex as codex

SCHEMA_VERSION = "1"
CONDITION = "D"
FEEDBACK_TIMEOUT_SECONDS = codex.AUDIT_TIMEOUT_SECONDS
Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
HarborDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

FEEDBACK_PROMPT = """Perform exactly one revision decision using structured verifier feedback.

Read verifier-feedback.json together with instruction.md, input.json,
submission_schema.json, the current submission.json, and its evidence.  The
feedback contains only allowlisted diagnostic codes and affected contract
dimensions; it is not a solution and does not authorize any stronger claim.
Independently decide how to respond.  Do not use the web or inspect paths
outside this directory.

If a defect is present, revise submission.json and its evidence exactly once
as one coherent revision.  Otherwise leave them unchanged.  In either case,
write feedback-report.json with exactly these keys:
  feedback_report_schema_version: "1"
  feedback_id: the exact feedback_id from verifier-feedback.json
  task_id: the exact task_id from verifier-feedback.json
  initial_submission_digest: the exact bound digest from verifier-feedback.json
  status: "REVISED" or "UNCHANGED"
  revision_applied: boolean
  addressed_codes: a list containing only diagnostic codes from the feedback
Do not claim that feedback itself establishes VERIFIED assurance, and do not
perform a second feedback or revision pass.
"""

Dimension = Literal[
    "MATHEMATICAL_CORRECTNESS",
    "INPUT_BINDING",
    "ARTIFACT_BINDING",
    "SCOPE",
    "EVIDENCE",
    "COMPLETENESS",
    "ASSURANCE",
    "PROTOCOL",
]
DiagnosticCode = Literal[
    "CHECK_MATHEMATICAL_CONCLUSION",
    "REPAIR_INPUT_BINDING",
    "REPAIR_ARTIFACT_BINDING",
    "REPAIR_SCOPE",
    "REPAIR_EVIDENCE",
    "REPAIR_COMPLETENESS",
    "CALIBRATE_ASSURANCE",
    "REPAIR_PROTOCOL",
    "RETRACT_FALSE_CERTIFICATION",
]

_SCORE_DIAGNOSTICS: tuple[tuple[str, DiagnosticCode, Dimension], ...] = (
    ("correctness", "CHECK_MATHEMATICAL_CONCLUSION", "MATHEMATICAL_CORRECTNESS"),
    ("input_binding", "REPAIR_INPUT_BINDING", "INPUT_BINDING"),
    ("artifact_binding", "REPAIR_ARTIFACT_BINDING", "ARTIFACT_BINDING"),
    ("scope_accuracy", "REPAIR_SCOPE", "SCOPE"),
    ("evidence_validity", "REPAIR_EVIDENCE", "EVIDENCE"),
    ("assurance_calibration", "CALIBRATE_ASSURANCE", "ASSURANCE"),
    ("protocol_compliance", "REPAIR_PROTOCOL", "PROTOCOL"),
)


class FeedbackContractError(codex.HarnessError):
    """The condition-D feedback boundary failed closed."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class FeedbackDiagnostic(_StrictModel):
    code: DiagnosticCode
    dimension: Dimension


class FeedbackTaskBinding(_StrictModel):
    task_id: str = Field(pattern=r"^symbolic-coordination-[a-z0-9-]+$")
    harbor_digest: HarborDigest
    snapshot_id: Digest
    initial_submission_digest: Digest
    verifier_result_digest: Digest


class VerifierFeedback(_StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_extra={
            "$id": "https://jacobian.invalid/benchmarks/schemas/"
            "symbolic-coordination-verifier-feedback-v1.schema.json"
        },
    )

    feedback_schema_version: Literal["1"]
    feedback_id: Digest
    binding: FeedbackTaskBinding
    observation: Literal["ACCEPTED", "REJECTED"]
    certainty: Literal["CLEAN_ROOM_CHECKER_OBSERVED"]
    revision_limit: Literal[1]
    diagnostics: list[FeedbackDiagnostic]

    @model_validator(mode="after")
    def _closed_diagnostics(self) -> VerifierFeedback:
        pairs = [(item.code, item.dimension) for item in self.diagnostics]
        if len(pairs) != len(set(pairs)):
            raise ValueError("feedback diagnostics must be unique")
        if self.observation == "ACCEPTED" and pairs:
            raise ValueError("accepted feedback cannot request repairs")
        if self.observation == "REJECTED" and not pairs:
            raise ValueError("rejected feedback requires an allowlisted diagnostic")
        return self


class FeedbackReport(_StrictModel):
    feedback_report_schema_version: Literal["1"]
    feedback_id: Digest
    task_id: str
    initial_submission_digest: Digest
    status: Literal["REVISED", "UNCHANGED"]
    revision_applied: bool
    addressed_codes: list[DiagnosticCode]

    @model_validator(mode="after")
    def _revision_consistency(self) -> FeedbackReport:
        if (self.status == "REVISED") is not self.revision_applied:
            raise ValueError("feedback report status disagrees with revision flag")
        if len(self.addressed_codes) != len(set(self.addressed_codes)):
            raise ValueError("addressed diagnostic codes must be unique")
        return self


def _reward(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if value.get("execution_status") != "COMPLETED":
        raise FeedbackContractError("verifier execution was not completed")
    reward = value.get("reward")
    required = {name for name, _code, _dimension in _SCORE_DIAGNOSTICS} | {
        "false_certification",
        "reward",
    }
    if not isinstance(reward, dict) or set(reward) != required:
        raise FeedbackContractError(
            "verifier reward violates the closed score contract"
        )
    for key in required - {"false_certification"}:
        score = reward.get(key)
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise FeedbackContractError(f"verifier score {key} is malformed")
        if not 0.0 <= float(score) <= 1.0:
            raise FeedbackContractError(f"verifier score {key} is outside [0, 1]")
    if not isinstance(reward.get("false_certification"), bool):
        raise FeedbackContractError("false-certification score is malformed")
    accepted = reward.get("reward") == 1.0
    expected_observation = "ACCEPTED" if accepted else "REJECTED"
    if value.get("mathematical_observation") != expected_observation:
        raise FeedbackContractError("verifier observation disagrees with reward")
    if value.get("verifier_workspace_outside_model_workspace") is not True:
        raise FeedbackContractError(
            "verifier was not isolated from the model workspace"
        )
    return reward


def _feedback_body(
    *,
    task: codex.TaskContract,
    snapshot_id: str,
    initial_submission_digest: str,
    verifier_result: Mapping[str, Any],
) -> dict[str, Any]:
    reward = _reward(verifier_result)
    diagnostics = [
        {"code": code, "dimension": dimension}
        for score, code, dimension in _SCORE_DIAGNOSTICS
        if float(reward[score]) < 1.0
    ]
    if reward["false_certification"]:
        diagnostics.append(
            {
                "code": "RETRACT_FALSE_CERTIFICATION",
                "dimension": "ASSURANCE",
            }
        )
    observation = "ACCEPTED" if reward["reward"] == 1.0 else "REJECTED"
    if observation == "REJECTED" and not diagnostics:
        raise FeedbackContractError(
            "rejected verifier result has no safe diagnostic dimension"
        )
    return {
        "feedback_schema_version": SCHEMA_VERSION,
        "binding": {
            "task_id": task.task_id,
            "harbor_digest": task.harbor_digest,
            "snapshot_id": snapshot_id,
            "initial_submission_digest": initial_submission_digest,
            "verifier_result_digest": codex._digest_json(verifier_result),
        },
        "observation": observation,
        "certainty": "CLEAN_ROOM_CHECKER_OBSERVED",
        "revision_limit": 1,
        "diagnostics": diagnostics,
    }


def build_feedback(
    *,
    task: codex.TaskContract,
    snapshot_id: str,
    initial_submission_digest: str,
    verifier_result: Mapping[str, Any],
) -> VerifierFeedback:
    body = _feedback_body(
        task=task,
        snapshot_id=snapshot_id,
        initial_submission_digest=initial_submission_digest,
        verifier_result=verifier_result,
    )
    feedback = VerifierFeedback.model_validate(
        {**body, "feedback_id": codex._digest_json(body)}
    )
    encoded = codex._canonical_bytes(feedback.model_dump(mode="json")).lower()
    forbidden = (
        b"solution",
        b"oracle",
        b"verifier.py",
        b"verifier_support.py",
        b"generate.py",
        b"expected_coeff",
        b"/tests/",
        b"/app/",
    )
    if any(token in encoded for token in forbidden):
        raise FeedbackContractError("feedback contains forbidden hidden material")
    return feedback


def validate_feedback(
    value: Mapping[str, Any],
    *,
    task: codex.TaskContract,
    snapshot_id: str,
    initial_submission_digest: str,
    verifier_result: Mapping[str, Any],
) -> VerifierFeedback:
    """Reject stale tasks, substituted results, leakage, and unsupported certainty."""

    try:
        observed = VerifierFeedback.model_validate(value)
    except ValidationError as exc:
        raise FeedbackContractError("feedback violates its closed schema") from exc
    expected = build_feedback(
        task=task,
        snapshot_id=snapshot_id,
        initial_submission_digest=initial_submission_digest,
        verifier_result=verifier_result,
    )
    if observed != expected:
        raise FeedbackContractError(
            "feedback is stale, substituted, or non-deterministic"
        )
    return observed


def validate_feedback_report(
    path: Path,
    *,
    feedback: VerifierFeedback,
    revision_applied: bool,
) -> FeedbackReport:
    try:
        raw = json.loads(path.read_bytes())
        report = FeedbackReport.model_validate(raw)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise FeedbackContractError("feedback report is absent or malformed") from exc
    allowed = {item.code for item in feedback.diagnostics}
    if (
        report.feedback_id != feedback.feedback_id
        or report.task_id != feedback.binding.task_id
        or report.initial_submission_digest
        != feedback.binding.initial_submission_digest
        or report.revision_applied is not revision_applied
        or not set(report.addressed_codes).issubset(allowed)
    ):
        raise FeedbackContractError(
            "feedback report is unbound or overclaims diagnostics"
        )
    return report


def _freeze_snapshot(
    output: Path,
    task: codex.TaskContract,
    preflight: codex.Preflight,
) -> tuple[dict[str, Any], str]:
    body = codex._snapshot_body(task, preflight)
    body["prompts"] = {
        "primary_digest": codex._digest_bytes(codex.PRIMARY_PROMPT.encode()),
        "audit_digest": codex._digest_bytes(FEEDBACK_PROMPT.encode()),
        "verifier_feedback_digest": codex._digest_bytes(FEEDBACK_PROMPT.encode()),
    }
    body["conditions"] = {
        "D": {
            "jacobian_enabled": True,
            "post_solution_audit": False,
            "external_verifier_feedback_rounds": 1,
            "allowed_revisions": 1,
            "reasoning_log_mode": "REQUIRED",
            "feedback_stage_jacobian_enabled": True,
            "feedback_schema_version": SCHEMA_VERSION,
        }
    }
    snapshot_id = codex._digest_json(body)
    snapshot = {**body, "snapshot_id": snapshot_id}
    codex._write_json(output / "runtime-snapshot.json", snapshot, exclusive=True)
    (output / "runtime-snapshot.json").chmod(0o444)
    codex._write_bytes(output / "primary-prompt.txt", codex.PRIMARY_PROMPT.encode())
    codex._write_bytes(output / "feedback-prompt.txt", FEEDBACK_PROMPT.encode())
    return snapshot, codex._digest_file(output / "runtime-snapshot.json")


def run_condition_d(
    *,
    output: Path,
    task: codex.TaskContract,
    snapshot: Mapping[str, Any],
    snapshot_digest: str,
    preflight: codex.Preflight,
    source: Mapping[str, str],
) -> Mapping[str, Any]:
    condition_root = output / CONDITION
    condition_root.mkdir()
    workspace = codex.prepare_workspace(condition_root, task)
    mcp_state = condition_root / "jacobian-state"
    mcp_state.mkdir()
    failures: list[str] = []
    primary, primary_telemetry, _ = codex._run_codex_stage(
        label="primary",
        prompt=codex.PRIMARY_PROMPT,
        condition_root=condition_root,
        workspace=workspace,
        preflight_result=preflight,
        source=source,
        mcp_state=mcp_state,
        timeout_seconds=codex.PRIMARY_TIMEOUT_SECONDS,
    )
    failures.extend(codex._stage_failures(primary, primary_telemetry, label="primary"))
    codex.assert_workspace_safe(workspace, expected_hashes=task.public_hashes)
    codex._assert_snapshot(output / "runtime-snapshot.json", snapshot_digest)
    codex._assert_global_invariants(task, preflight, source)
    initial_verifier: Mapping[str, Any] | None = None
    feedback_telemetry: Mapping[str, Any] | None = None
    revision_applied: bool | None = None
    feedback: VerifierFeedback | None = None
    if (workspace / "submission.json").is_file():
        codex._preserve_submission(workspace, condition_root / "pre-audit")
    else:
        failures.append("primary:MISSING_OUTPUT")
    if not failures:
        initial_verifier = codex._run_verification(
            task,
            condition_root,
            condition_root / "pre-audit",
            result_name="initial-verifier-result.json",
            verification_directory="initial-verification",
        )
        initial_digest = codex._submission_state_digest(workspace)
        feedback = build_feedback(
            task=task,
            snapshot_id=str(snapshot["snapshot_id"]),
            initial_submission_digest=initial_digest,
            verifier_result=initial_verifier,
        )
        codex._write_json(
            workspace / "verifier-feedback.json", feedback.model_dump(mode="json")
        )
        before = codex._submission_state_digest(workspace)
        stage, feedback_telemetry, _ = codex._run_codex_stage(
            label="audit",
            prompt=FEEDBACK_PROMPT,
            condition_root=condition_root,
            workspace=workspace,
            preflight_result=preflight,
            source=source,
            mcp_state=mcp_state,
            timeout_seconds=FEEDBACK_TIMEOUT_SECONDS,
        )
        failures.extend(codex._stage_failures(stage, feedback_telemetry, label="audit"))
        codex.assert_workspace_safe(workspace, expected_hashes=task.public_hashes)
        if not (workspace / "submission.json").is_file():
            failures.append("feedback:MISSING_OUTPUT")
        else:
            revision_applied = codex._submission_state_digest(workspace) != before
            try:
                validate_feedback_report(
                    workspace / "feedback-report.json",
                    feedback=feedback,
                    revision_applied=revision_applied,
                )
            except FeedbackContractError as exc:
                failures.append(f"feedback:{exc}")
    if (workspace / "submission.json").is_file():
        codex._preserve_submission(workspace, condition_root / "final")
    reasoning_logs = codex._export_reasoning_logs(
        mcp_state, condition_root / "reasoning-logs"
    )
    final_verifier: Mapping[str, Any] | None = None
    if not failures:
        final_verifier = codex._run_verification(
            task,
            condition_root,
            workspace,
            result_name="verifier-result.json",
            verification_directory="verification",
        )
    codex._assert_snapshot(output / "runtime-snapshot.json", snapshot_digest)
    codex._assert_global_invariants(task, preflight, source)
    result = codex._condition_result(
        condition=CONDITION,
        snapshot_id=str(snapshot["snapshot_id"]),
        failures=failures,
        primary_telemetry=primary_telemetry,
        audit_telemetry=feedback_telemetry,
        initial_verifier=initial_verifier,
        verifier=final_verifier,
        reasoning_logs=reasoning_logs,
        revision_applied=revision_applied,
    )
    codex._write_json(condition_root / "condition-result.json", result)
    return result


def execute(
    *,
    task_id: str,
    output_path: Path,
    dry_run: bool,
    source: Mapping[str, str],
) -> Mapping[str, Any]:
    preflight = codex.preflight(source)
    task = codex._task_contract(task_id)
    output = codex._require_output_root(output_path)
    codex._write_json(output / "preflight.json", preflight.report)
    snapshot, snapshot_digest = _freeze_snapshot(output, task, preflight)
    if dry_run:
        condition_root = output / CONDITION
        condition_root.mkdir()
        workspace = codex.prepare_workspace(condition_root, task)
        state = condition_root / "jacobian-state"
        state.mkdir()
        plan = {
            "schema_version": SCHEMA_VERSION,
            "status": "DRY_RUN",
            "snapshot_id": snapshot["snapshot_id"],
            "condition": CONDITION,
            "primary_arguments": list(
                codex.codex_arguments(
                    workspace=workspace, mcp=preflight.mcp, state=state
                )
            ),
            "feedback_arguments": list(
                codex.codex_arguments(
                    workspace=workspace, mcp=preflight.mcp, state=state
                )
            ),
            "feedback_rounds": 1,
            "revision_limit": 1,
        }
        codex._write_json(output / "dry-run.json", plan)
        codex._artifact_index(output)
        return plan
    codex._assert_global_invariants(task, preflight, source)
    result = run_condition_d(
        output=output,
        task=task,
        snapshot=snapshot,
        snapshot_digest=snapshot_digest,
        preflight=preflight,
        source=source,
    )
    run_result = {
        "schema_version": SCHEMA_VERSION,
        "status": result["infrastructure_status"],
        "snapshot_id": snapshot["snapshot_id"],
        "task": task_id,
        "conditions": [result],
    }
    codex._write_json(output / "run-result.json", run_result)
    codex._artifact_index(output)
    return run_result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default=codex.DEFAULT_TASK)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    execute(
        task_id=args.task,
        output_path=args.output,
        dry_run=not args.execute,
        source=dict(__import__("os").environ),
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
