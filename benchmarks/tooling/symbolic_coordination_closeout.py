"""Frozen six-family A/B/C/D symbolic-coordination closeout observation."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import ConfigDict, Field, model_validator

from benchmarks.tooling import symbolic_coordination_codex as codex
from benchmarks.tooling import symbolic_coordination_comparison as comparison
from benchmarks.tooling import symbolic_coordination_feedback as feedback
from benchmarks.tooling import symbolic_coordination_trajectory as trajectory

SCHEMA_VERSION = "1"
RUNNER_CONTRACT_VERSION = "1"
Condition = Literal["A", "B", "C", "D"]
CONDITIONS: tuple[Condition, ...] = ("A", "B", "C", "D")
DEFAULT_TASKS = (
    "symbolic-coordination-valid-inverse-01",
    "symbolic-coordination-near-miss-01",
    "symbolic-coordination-one-direction-01",
    "symbolic-coordination-keller-only-01",
    "symbolic-coordination-grid-exhausted-01",
    "symbolic-coordination-semantic-equivalence-01",
)
EXPECTED_FAMILIES = frozenset(
    {
        "valid-two-sided-inverse",
        "perturbed-near-miss",
        "one-direction-only-evidence",
        "constant-nonzero-jacobian",
        "bounded-collision-scope",
        "semantic-equivalence",
    }
)
ORDER_PERMUTATIONS: tuple[tuple[Condition, ...], ...] = (
    ("A", "B", "D", "C"),
    ("B", "C", "A", "D"),
    ("C", "D", "B", "A"),
    ("D", "A", "C", "B"),
    ("A", "C", "D", "B"),
    ("D", "B", "A", "C"),
)


class CloseoutError(comparison.ComparisonError):
    """The final closeout contract or its evidence failed closed."""


class ContractVersions(comparison._StrictModel):
    closeout_manifest: Literal["1"]
    closeout_report: Literal["1"]
    verifier_feedback: Literal["1"]
    trajectory_telemetry: Literal["1"]
    runner: Literal["1"]


class ConditionD(comparison._StrictModel):
    jacobian_enabled: Literal[True]
    post_solution_audit: Literal[False]
    external_verifier_feedback_rounds: Literal[1]
    allowed_revisions: Literal[1]
    reasoning_log_mode: Literal["REQUIRED"]
    feedback_stage_jacobian_enabled: Literal[True]
    feedback_schema_version: Literal["1"]


class ConditionBindings(comparison._StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )

    condition_a: comparison.ConditionA = Field(alias="A")
    condition_b: comparison.ConditionB = Field(alias="B")
    condition_c: comparison.ConditionC = Field(alias="C")
    condition_d: ConditionD = Field(alias="D")


class PromptBindings(comparison._StrictModel):
    primary: comparison.Digest
    audit: comparison.Digest
    verifier_feedback: comparison.Digest


class McpBinding(comparison._StrictModel):
    executable_digest: comparison.Digest
    policy_profile: Literal["COMPUTE_VERIFY_NO_RETRIEVAL"]
    primary_conditions: list[Condition]
    c_audit_stage_enabled: Literal[False]
    d_feedback_stage_enabled: Literal[True]

    @model_validator(mode="after")
    def _scope(self) -> McpBinding:
        if self.primary_conditions != ["B", "C", "D"]:
            raise ValueError("MCP primary scope must be exactly B/C/D")
        return self


class RunUnit(comparison._StrictModel):
    sequence: int = Field(ge=0)
    run_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]+$")
    task_id: str
    representative: Literal[1]
    condition: Condition
    block_position: int = Field(ge=0, le=3)
    run_relpath: str = Field(pattern=r"^runs/[a-z0-9][a-z0-9-]+$")


class CloseoutManifest(comparison._StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_extra={
            "$id": "https://jacobian.invalid/benchmarks/schemas/"
            "symbolic-coordination-closeout-experiment-v1.schema.json"
        },
    )

    schema_version: Literal["1"]
    contract_versions: ContractVersions
    experiment_id: comparison.Digest
    created_at: str
    evidence_class: Literal["host-local-workflow-observation"]
    causal_claim_authorized: Literal[False]
    source_revision: comparison.Revision
    source_branch: str
    stack_revisions: dict[str, comparison.Revision]
    dataset_id: Literal["symbolic-coordination-v1"]
    tasks: list[comparison.TaskBinding]
    representatives_per_family: Literal[1]
    conditions: ConditionBindings
    model: comparison.ModelBinding
    model_contract_digest: comparison.Digest
    reasoning_effort: str
    codex: comparison.CodexBinding
    auth: comparison.AuthBinding
    prompt_digests: PromptBindings
    budgets: comparison.BudgetBindings
    mcp: McpBinding
    runtime: comparison.RuntimeBinding
    order_method: Literal["balanced-six-block-permutation-v1"]
    retry_policy: Literal["PRE_MODEL_OR_INFRASTRUCTURE_ONLY_NEVER_WRONG_ANSWER"]
    runs: list[RunUnit]

    @model_validator(mode="after")
    def _invariants(self) -> CloseoutManifest:
        if self.stack_revisions.get("pr5") != self.source_revision:
            raise ValueError("stack revision pr5 must equal source revision")
        families = [task.family for task in self.tasks]
        if len(self.tasks) != 6 or frozenset(families) != EXPECTED_FAMILIES:
            raise ValueError("manifest must bind one task from each pilot family")
        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("representative task bindings must be unique")
        if len(self.runs) != 24 or [run.sequence for run in self.runs] != list(
            range(24)
        ):
            raise ValueError("closeout must contain exactly 24 ordered condition runs")
        for task_id in task_ids:
            block = [run for run in self.runs if run.task_id == task_id]
            if {run.condition for run in block} != set(CONDITIONS):
                raise ValueError("each representative must contain exactly A/B/C/D")
            if sorted(run.block_position for run in block) != [0, 1, 2, 3]:
                raise ValueError("condition-order block is malformed")
        if self.budgets.condition_runs.value != 24:
            raise ValueError("condition-run budget must be exactly 24")
        return self


class CloseoutRunObservation(comparison.RunObservation):
    condition: Condition  # type: ignore[assignment]
    initial_verifier_available: bool
    initial_accepted: bool | None
    initial_reward: float | None = Field(default=None, ge=0, le=1)
    initial_correctness: float | None = Field(default=None, ge=0, le=1)
    initial_evidence_validity: float | None = Field(default=None, ge=0, le=1)
    initial_scope_accuracy: float | None = Field(default=None, ge=0, le=1)
    initial_assurance_calibration: float | None = Field(default=None, ge=0, le=1)
    initial_input_binding: float | None = Field(default=None, ge=0, le=1)
    initial_artifact_binding: float | None = Field(default=None, ge=0, le=1)
    initial_protocol_compliance: float | None = Field(default=None, ge=0, le=1)
    initial_false_certification: bool | None
    feedback_outcome: Literal[
        "NOT_APPLICABLE",
        "REPAIR",
        "UNCHANGED_FAILURE",
        "REGRESSION",
        "ALREADY_CORRECT",
        "INCOMPLETE",
        "UNAVAILABLE",
    ]


class CloseoutConditionSummary(comparison.ConditionSummary):
    condition: Condition  # type: ignore[assignment]


class CloseoutPairedComparison(comparison.PairedComparison):
    contrast: Literal["A_TO_B", "B_TO_C", "B_TO_D", "C_TO_D"]  # type: ignore[assignment]
    left: Condition  # type: ignore[assignment]
    right: Condition  # type: ignore[assignment]


class FamilyTrajectorySummary(comparison._StrictModel):
    task_id: str
    task_family: str
    initial_acceptance: dict[Condition, bool | None]
    final_acceptance: dict[Condition, bool | None]
    feedback_outcome: Literal[
        "REPAIR",
        "UNCHANGED_FAILURE",
        "REGRESSION",
        "ALREADY_CORRECT",
        "INCOMPLETE",
        "UNAVAILABLE",
    ]
    invocation_calls: dict[Condition, int | None]
    reasoning_compliance: dict[Condition, comparison.ReasoningCompliance]
    protocol_violations: dict[Condition, list[str]]


class CloseoutReport(comparison._StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_extra={
            "$id": "https://jacobian.invalid/benchmarks/schemas/"
            "symbolic-coordination-closeout-report-v1.schema.json"
        },
    )

    schema_version: Literal["1"]
    contract_versions: ContractVersions
    report_id: comparison.Digest
    manifest_id: comparison.Digest
    evidence_class: Literal["host-local-workflow-observation"]
    causal_claim_authorized: Literal[False]
    interpretation: Literal["descriptive-closeout-pilot"]
    collection_status: Literal["COMPLETE", "PARTIAL"]
    planned_runs: Literal[24]
    observed_runs: int = Field(ge=0, le=24)
    pre_model_failures: int = Field(ge=0, le=24)
    missing_runs: int = Field(ge=0, le=24)
    acquisition_completion: comparison.Rate
    infrastructure_failure: comparison.Rate
    records: list[CloseoutRunObservation]
    conditions: list[CloseoutConditionSummary]
    paired: list[CloseoutPairedComparison]
    family_trajectories: list[FamilyTrajectorySummary]
    limitations: list[str]

    @model_validator(mode="after")
    def _coverage(self) -> CloseoutReport:
        if len(self.records) != 24 or len(self.conditions) != 4:
            raise ValueError("closeout report coverage is incomplete")
        if [item.condition for item in self.conditions] != list(CONDITIONS):
            raise ValueError("condition summaries must be ordered A/B/C/D")
        if [item.contrast for item in self.paired] != [
            "A_TO_B",
            "B_TO_C",
            "B_TO_D",
            "C_TO_D",
        ]:
            raise ValueError("paired contrasts are incomplete")
        if len(self.family_trajectories) != 6:
            raise ValueError("one trajectory summary per family is required")
        return self


def counterbalanced_runs(task_ids: Sequence[str]) -> list[RunUnit]:
    if len(task_ids) != 6 or len(set(task_ids)) != 6:
        raise CloseoutError("closeout requires exactly six unique representatives")
    runs: list[RunUnit] = []
    sequence = 0
    for task_index, task_id in enumerate(task_ids):
        for position, condition in enumerate(ORDER_PERMUTATIONS[task_index]):
            run_id = f"r1-{task_id}-{condition.lower()}"
            runs.append(
                RunUnit(
                    sequence=sequence,
                    run_id=run_id,
                    task_id=task_id,
                    representative=1,
                    condition=condition,
                    block_position=position,
                    run_relpath=f"runs/{run_id}",
                )
            )
            sequence += 1
    return runs


def _conditions() -> dict[str, Any]:
    base = codex._snapshot_body  # retain an explicit link to the frozen PR2 contract
    del base
    return {
        "A": {
            "jacobian_enabled": False,
            "post_solution_audit": False,
            "reasoning_log_mode": "OFF",
        },
        "B": {
            "jacobian_enabled": True,
            "post_solution_audit": False,
            "reasoning_log_mode": "REQUIRED",
        },
        "C": {
            "jacobian_enabled": True,
            "post_solution_audit": True,
            "audit_passes": 1,
            "allowed_revisions": 1,
            "reasoning_log_mode": "REQUIRED",
            "audit_stage_jacobian_enabled": False,
        },
        "D": {
            "jacobian_enabled": True,
            "post_solution_audit": False,
            "external_verifier_feedback_rounds": 1,
            "allowed_revisions": 1,
            "reasoning_log_mode": "REQUIRED",
            "feedback_stage_jacobian_enabled": True,
            "feedback_schema_version": "1",
        },
    }


def create_manifest(
    *,
    output: Path,
    task_ids: Sequence[str],
    stack_revisions: Mapping[str, str],
    source: Mapping[str, str],
) -> CloseoutManifest:
    if output.exists() or codex.ROOT in output.resolve().parents:
        raise CloseoutError("output must be a new directory outside the repository")
    preflight = codex.preflight(source)
    contracts = [codex._task_contract(task_id) for task_id in task_ids]
    tasks = [
        comparison.TaskBinding(
            task_id=item.task_id,
            family=comparison._task_family(item),
            harbor_digest=item.harbor_digest,
            public_file_hashes=dict(item.public_hashes),
            verifier_hashes=dict(item.verifier_hashes),
        )
        for item in contracts
    ]
    budgets = comparison.BudgetBindings(
        primary_wall_seconds=comparison.BudgetValue(
            availability="EXACT", value=codex.PRIMARY_TIMEOUT_SECONDS, unit="seconds"
        ),
        audit_wall_seconds=comparison.BudgetValue(
            availability="EXACT", value=codex.AUDIT_TIMEOUT_SECONDS, unit="seconds"
        ),
        tokens_per_stage=comparison.BudgetValue(
            availability="EXACT", value=codex.MAX_TOTAL_TOKENS, unit="tokens"
        ),
        tool_calls_per_stage=comparison.BudgetValue(
            availability="UNBOUNDED", value=None, unit="calls"
        ),
        cost=comparison.BudgetValue(availability="UNAVAILABLE", value=None, unit="USD"),
        condition_runs=comparison.BudgetValue(
            availability="EXACT", value=24, unit="condition-runs"
        ),
    )
    preflight_report = preflight.report
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "contract_versions": {
            "closeout_manifest": "1",
            "closeout_report": "1",
            "verifier_feedback": "1",
            "trajectory_telemetry": trajectory.SCHEMA_VERSION,
            "runner": RUNNER_CONTRACT_VERSION,
        },
        "created_at": datetime.now(UTC).isoformat(),
        "evidence_class": "host-local-workflow-observation",
        "causal_claim_authorized": False,
        "source_revision": preflight.source_revision,
        "source_branch": preflight.branch,
        "stack_revisions": dict(sorted(stack_revisions.items())),
        "dataset_id": codex.DATASET_ID,
        "tasks": [item.model_dump(mode="json") for item in tasks],
        "representatives_per_family": 1,
        "conditions": _conditions(),
        "model": dict(preflight.selected_model),
        "model_contract_digest": preflight.selected_model_digest,
        "reasoning_effort": codex.DEFAULT_REASONING_EFFORT,
        "codex": {
            "version": preflight.codex_version,
            "executable_digest": codex._digest_file(preflight.codex),
            "ignore_user_config": True,
            "ignore_rules": True,
        },
        "auth": {
            "mode": "chatgpt",
            "api_key": False,
            "ephemeral_session": True,
            "credential_material_recorded": False,
        },
        "prompt_digests": {
            "primary": codex._digest_bytes(codex.PRIMARY_PROMPT.encode()),
            "audit": codex._digest_bytes(codex.AUDIT_PROMPT.encode()),
            "verifier_feedback": codex._digest_bytes(feedback.FEEDBACK_PROMPT.encode()),
        },
        "budgets": budgets.model_dump(mode="json"),
        "mcp": {
            "executable_digest": codex._digest_file(preflight.mcp),
            "policy_profile": "COMPUTE_VERIFY_NO_RETRIEVAL",
            "primary_conditions": ["B", "C", "D"],
            "c_audit_stage_enabled": False,
            "d_feedback_stage_enabled": True,
        },
        "runtime": {
            "python": __import__("platform").python_version(),
            "platform": __import__("platform").platform(),
            "harbor_version": codex.HARBOR_VERSION,
            "uv_lock_digest": codex._digest_file(codex.ROOT / "uv.lock"),
            "pilot_manifest_digest": codex._digest_file(
                codex.DATASET / "pilot-manifest.json"
            ),
            "preflight_report_digest": comparison._digest(preflight_report),
            "sampling_seed": None,
            "sampling_temperature": None,
            "sampling_source": "codex-cli-chatgpt-defaults-no-cli-overrides",
        },
        "order_method": "balanced-six-block-permutation-v1",
        "retry_policy": "PRE_MODEL_OR_INFRASTRUCTURE_ONLY_NEVER_WRONG_ANSWER",
        "runs": [
            item.model_dump(mode="json") for item in counterbalanced_runs(task_ids)
        ],
    }
    manifest = CloseoutManifest.model_validate(
        {**body, "experiment_id": comparison._digest(body)}
    )
    output.mkdir(parents=True)
    comparison._write_exclusive(
        output / "experiment-manifest.json", manifest.model_dump(mode="json")
    )
    (output / "experiment-manifest.json").chmod(0o444)
    comparison._write_exclusive(output / "preflight.json", preflight_report)
    return manifest


def load_manifest(root: Path) -> CloseoutManifest:
    try:
        return CloseoutManifest.model_validate(
            comparison._read_json(root / "experiment-manifest.json")
        )
    except Exception as exc:
        raise CloseoutError("closeout manifest is absent or malformed") from exc


def _validate_current_contract(manifest: CloseoutManifest) -> None:
    revision, branch = codex._require_clean_source()
    if revision != manifest.source_revision or branch != manifest.source_branch:
        raise CloseoutError("current clean source does not match frozen manifest")
    expected_prompts = {
        "primary": codex._digest_bytes(codex.PRIMARY_PROMPT.encode()),
        "audit": codex._digest_bytes(codex.AUDIT_PROMPT.encode()),
        "verifier_feedback": codex._digest_bytes(feedback.FEEDBACK_PROMPT.encode()),
    }
    if manifest.prompt_digests.model_dump(mode="json") != expected_prompts:
        raise CloseoutError("prompt contract drifted")
    if (
        manifest.model.slug != codex.DEFAULT_MODEL
        or manifest.reasoning_effort != codex.DEFAULT_REASONING_EFFORT
    ):
        raise CloseoutError("model or reasoning contract drifted")
    for bound in manifest.tasks:
        actual = codex._task_contract(bound.task_id)
        if (
            actual.harbor_digest != bound.harbor_digest
            or dict(actual.public_hashes) != bound.public_file_hashes
            or dict(actual.verifier_hashes) != bound.verifier_hashes
        ):
            raise CloseoutError(f"task contract drift: {bound.task_id}")


def _record_matches_unit(
    root: Path, manifest: CloseoutManifest, unit: RunUnit
) -> trajectory.RunTelemetry:
    try:
        records = trajectory.analyze_run(root)
    except Exception as exc:
        raise CloseoutError(f"corrupt run artifacts for {unit.run_id}: {exc}") from exc
    if len(records) != 1:
        raise CloseoutError(f"run {unit.run_id} must contain one condition")
    record = records[0]
    if (
        record.task_id != unit.task_id
        or record.condition != unit.condition
        or record.source_revision != manifest.source_revision
        or record.model != manifest.model.slug
        or record.reasoning_effort != manifest.reasoning_effort
    ):
        raise CloseoutError(f"run identity drift: {unit.run_id}")
    snapshot = comparison._read_json(root / "runtime-snapshot.json")
    prompt = "verifier_feedback" if unit.condition == "D" else "audit"
    actual_digest = snapshot.get("prompts", {}).get("audit_digest")
    expected_digest = getattr(manifest.prompt_digests, prompt)
    if actual_digest != expected_digest:
        raise CloseoutError(f"second-stage prompt binding drift: {unit.run_id}")
    task = next(item for item in manifest.tasks if item.task_id == unit.task_id)
    if snapshot.get("task", {}).get("harbor_digest") != task.harbor_digest:
        raise CloseoutError(f"task digest drift: {unit.run_id}")
    if unit.condition == "D":
        condition_root = root / "D"
        initial = comparison._read_json(condition_root / "initial-verifier-result.json")
        raw_feedback = comparison._read_json(
            condition_root / "workspace" / "verifier-feedback.json"
        )
        contract = codex._task_contract(unit.task_id)
        validated = feedback.validate_feedback(
            raw_feedback,
            task=contract,
            snapshot_id=str(snapshot["snapshot_id"]),
            initial_submission_digest=str(
                raw_feedback.get("binding", {}).get("initial_submission_digest")
            ),
            verifier_result=initial,
        )
        actual_initial_digest = codex._submission_state_digest(
            condition_root / "pre-audit"
        )
        if validated.binding.initial_submission_digest != actual_initial_digest:
            raise CloseoutError("D feedback is bound to a stale initial submission")
        feedback.validate_feedback_report(
            condition_root / "workspace" / "feedback-report.json",
            feedback=validated,
            revision_applied=cast(bool, record.audit.revision_applied),
        )
    return record


def run_experiment(
    root: Path,
    *,
    source: Mapping[str, str],
    max_model_executions: int | None,
    retry_infrastructure: bool = False,
) -> dict[str, int]:
    manifest = load_manifest(root)
    _validate_current_contract(manifest)
    observed = 0
    executed = 0
    incomplete = 0
    for unit in manifest.runs:
        run_root = root / unit.run_relpath
        failure_path = root / "pre-model-failures" / f"{unit.run_id}.json"
        if run_root.exists():
            record = _record_matches_unit(run_root, manifest, unit)
            if record.infrastructure_status != "INCOMPLETE" or not retry_infrastructure:
                observed += 1
                incomplete += record.infrastructure_status == "INCOMPLETE"
                continue
            history = root / "retry-history" / unit.run_id
            history.mkdir(parents=True, exist_ok=True)
            attempt = len(list(history.glob("run-attempt-*"))) + 1
            run_root.rename(history / f"run-attempt-{attempt:03d}")
        elif failure_path.exists():
            comparison._load_pre_model_failure(failure_path)
            if not retry_infrastructure:
                incomplete += 1
                continue
            history = root / "retry-history" / unit.run_id
            history.mkdir(parents=True, exist_ok=True)
            attempt = len(list(history.glob("pre-model-attempt-*.json"))) + 1
            failure_path.rename(history / f"pre-model-attempt-{attempt:03d}.json")
        if max_model_executions is not None and executed >= max_model_executions:
            break
        try:
            if unit.condition == "D":
                feedback.execute(
                    task_id=unit.task_id,
                    output_path=run_root,
                    dry_run=False,
                    source=source,
                )
            else:
                codex.execute(
                    task_id=unit.task_id,
                    output_path=run_root,
                    conditions=[unit.condition],
                    dry_run=False,
                    source=source,
                )
            record = _record_matches_unit(run_root, manifest, unit)
        except Exception as exc:
            if run_root.exists():
                raise
            body = {
                "schema_version": "1",
                "run_id": unit.run_id,
                "classification": "PRE_MODEL_FAILURE",
                "exception_type": type(exc).__name__,
                "message": str(exc),
            }
            failure = comparison.PreModelFailure.model_validate(
                {**body, "failure_id": comparison._digest(body)}
            )
            comparison._write_exclusive(
                root / "pre-model-failures" / f"{unit.run_id}.json",
                failure.model_dump(mode="json"),
            )
            raise CloseoutError(f"pre-model failure for {unit.run_id}: {exc}") from exc
        executed += 1
        observed += 1
        incomplete += record.infrastructure_status == "INCOMPLETE"
    return {
        "observed": observed,
        "executed": executed,
        "infrastructure_incomplete": incomplete,
    }


def _base_observation(
    manifest: CloseoutManifest,
    unit: RunUnit,
    record: trajectory.RunTelemetry | None,
    acquisition: Literal["OBSERVED", "PRE_MODEL_FAILURE", "MISSING"],
    failures: Sequence[str] = (),
) -> dict[str, Any]:
    mapped = comparison.RunUnit(
        sequence=unit.sequence,
        run_id=unit.run_id,
        task_id=unit.task_id,
        repetition=0,
        condition="C" if unit.condition == "D" else unit.condition,
        block_position=min(unit.block_position, 2),
        run_relpath=unit.run_relpath,
    )
    value = comparison._observation(
        cast(Any, manifest), mapped, record, acquisition, failures
    ).model_dump(mode="json")
    value["condition"] = unit.condition
    initial = record.audit.initial_verifier if record is not None else None
    value.update(
        {
            "initial_verifier_available": initial is not None,
            "initial_accepted": initial.reward == 1.0 if initial else None,
            "initial_reward": initial.reward if initial else None,
            "initial_correctness": initial.correctness if initial else None,
            "initial_evidence_validity": initial.evidence_validity if initial else None,
            "initial_scope_accuracy": initial.scope_accuracy if initial else None,
            "initial_assurance_calibration": initial.assurance_calibration
            if initial
            else None,
            "initial_input_binding": initial.input_binding if initial else None,
            "initial_artifact_binding": initial.artifact_binding if initial else None,
            "initial_protocol_compliance": initial.protocol_compliance
            if initial
            else None,
            "initial_false_certification": initial.false_certification
            if initial
            else None,
            "feedback_outcome": record.audit.classification
            if record is not None and unit.condition == "D"
            else ("NOT_APPLICABLE" if record is not None else "UNAVAILABLE"),
        }
    )
    return value


def _condition_summary(
    condition: Condition, records: Sequence[CloseoutRunObservation]
) -> CloseoutConditionSummary:
    selected = [item for item in records if item.condition == condition]
    mapped = []
    for item in selected:
        raw = item.model_dump(
            mode="json",
            exclude={
                "initial_verifier_available",
                "initial_accepted",
                "initial_reward",
                "initial_correctness",
                "initial_evidence_validity",
                "initial_scope_accuracy",
                "initial_assurance_calibration",
                "initial_input_binding",
                "initial_artifact_binding",
                "initial_protocol_compliance",
                "initial_false_certification",
                "feedback_outcome",
            },
        )
        raw["condition"] = "C" if condition == "D" else condition
        mapped.append(comparison.RunObservation.model_validate(raw))
    base = comparison._condition_summary(
        "C" if condition == "D" else condition, mapped
    ).model_dump(mode="json")
    base["condition"] = condition
    return CloseoutConditionSummary.model_validate(base)


def _paired(
    records: Sequence[CloseoutRunObservation], left: Condition, right: Condition
) -> CloseoutPairedComparison:
    indexed = {(item.task_id, item.condition): item for item in records}
    counts: Counter[str] = Counter()
    for task_id in sorted({item.task_id for item in records}):
        a = indexed[(task_id, left)].accepted
        b = indexed[(task_id, right)].accepted
        if a is None or b is None:
            counts["missing"] += 1
        elif not a and not b:
            counts["both_failed"] += 1
        elif a and not b:
            counts["left_only"] += 1
        elif not a and b:
            counts["right_only"] += 1
        else:
            counts["both_accepted"] += 1
    complete = 6 - counts["missing"]
    names = {
        ("A", "B"): "A_TO_B",
        ("B", "C"): "B_TO_C",
        ("B", "D"): "B_TO_D",
        ("C", "D"): "C_TO_D",
    }
    return CloseoutPairedComparison(
        contrast=cast(Any, names[(left, right)]),
        left=left,
        right=right,
        planned_pairs=6,
        complete_binary_pairs=complete,
        missing_pairs=counts["missing"],
        both_failed=counts["both_failed"],
        left_only_accepted=counts["left_only"],
        right_only_accepted=counts["right_only"],
        both_accepted=counts["both_accepted"],
        discordant_pairs=counts["left_only"] + counts["right_only"],
        acceptance_difference=(
            (counts["right_only"] - counts["left_only"]) / complete
            if complete
            else None
        ),
        exact_test="exact-paired-binomial-equivalent-to-mcnemar",
        exact_p_value=comparison._exact_p_value(
            counts["left_only"], counts["right_only"]
        )
        if complete
        else None,
        exact_test_status="AVAILABLE" if complete else "NO_COMPLETE_PAIRS",
    )


def build_report(root: Path) -> CloseoutReport:
    manifest = load_manifest(root)
    records: list[CloseoutRunObservation] = []
    for unit in manifest.runs:
        run_root = root / unit.run_relpath
        failure_path = root / "pre-model-failures" / f"{unit.run_id}.json"
        if run_root.exists():
            record = _record_matches_unit(run_root, manifest, unit)
            raw = _base_observation(manifest, unit, record, "OBSERVED")
        elif failure_path.exists():
            failure = comparison._load_pre_model_failure(failure_path)
            raw = _base_observation(
                manifest, unit, None, "PRE_MODEL_FAILURE", [failure.message]
            )
        else:
            raw = _base_observation(manifest, unit, None, "MISSING")
        records.append(CloseoutRunObservation.model_validate(raw))
    summaries = [_condition_summary(item, records) for item in CONDITIONS]
    family_trajectories = []
    for task in manifest.tasks:
        selected = {
            item.condition: item for item in records if item.task_id == task.task_id
        }
        d = selected["D"]
        family_trajectories.append(
            FamilyTrajectorySummary(
                task_id=task.task_id,
                task_family=task.family,
                initial_acceptance={
                    item: selected[item].initial_accepted for item in CONDITIONS
                },
                final_acceptance={item: selected[item].accepted for item in CONDITIONS},
                feedback_outcome=cast(Any, d.feedback_outcome),
                invocation_calls={
                    item: selected[item].invocation_calls for item in CONDITIONS
                },
                reasoning_compliance={
                    item: selected[item].reasoning_compliance for item in CONDITIONS
                },
                protocol_violations={
                    item: selected[item].protocol_violations for item in CONDITIONS
                },
            )
        )
    observed = sum(item.acquisition_status == "OBSERVED" for item in records)
    pre_model = sum(item.acquisition_status == "PRE_MODEL_FAILURE" for item in records)
    missing = sum(item.acquisition_status == "MISSING" for item in records)
    infra_failures = pre_model + sum(
        item.acquisition_status == "OBSERVED"
        and item.infrastructure_status == "INCOMPLETE"
        for item in records
    )
    body: dict[str, Any] = {
        "schema_version": "1",
        "contract_versions": manifest.contract_versions.model_dump(mode="json"),
        "manifest_id": manifest.experiment_id,
        "evidence_class": "host-local-workflow-observation",
        "causal_claim_authorized": False,
        "interpretation": "descriptive-closeout-pilot",
        "collection_status": "COMPLETE" if observed == 24 else "PARTIAL",
        "planned_runs": 24,
        "observed_runs": observed,
        "pre_model_failures": pre_model,
        "missing_runs": missing,
        "acquisition_completion": comparison._wilson(observed, 24).model_dump(
            mode="json"
        ),
        "infrastructure_failure": comparison._wilson(infra_failures, 24).model_dump(
            mode="json"
        ),
        "records": [item.model_dump(mode="json") for item in records],
        "conditions": [item.model_dump(mode="json") for item in summaries],
        "paired": [
            _paired(records, "A", "B").model_dump(mode="json"),
            _paired(records, "B", "C").model_dump(mode="json"),
            _paired(records, "B", "D").model_dump(mode="json"),
            _paired(records, "C", "D").model_dump(mode="json"),
        ],
        "family_trajectories": [
            item.model_dump(mode="json") for item in family_trajectories
        ],
        "limitations": [
            "This single-representative nondeterministic closeout is descriptive and does not identify causal lift or statistical significance.",
            "The six public pilot representatives are contaminated for future held-out capability evaluation.",
            "ChatGPT-authenticated Codex exposes no monetary cost, so cost remains explicitly unavailable.",
            "Unavailable telemetry is never imputed as zero, success, or mathematical failure.",
            "Condition D exposes only typed verifier dimensions; it cannot diagnose defects outside that allowlist.",
        ],
    }
    return CloseoutReport.model_validate(
        {**body, "report_id": comparison._digest(body)}
    )


def render_report(report: CloseoutReport) -> str:
    lines = [
        "# Symbolic coordination closeout",
        "",
        f"Collection: **{report.collection_status}** ({report.observed_runs}/{report.planned_runs})",
        "",
        "| Condition | Initial accepted | Final accepted | Final acceptance (95% Wilson) | Repairs | Unchanged | Regressions | Already correct | Tokens | Calls | Wall s | Cost |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for summary in report.conditions:
        selected = [
            item for item in report.records if item.condition == summary.condition
        ]
        initial = sum(item.initial_accepted is True for item in selected)
        rate = summary.acceptance
        interval = (
            "unavailable"
            if rate.value is None
            else f"{rate.numerator}/{rate.denominator} ({rate.wilson_low:.3f}-{rate.wilson_high:.3f})"
        )
        audit = summary.audit_classifications
        lines.append(
            f"| {summary.condition} | {initial}/{sum(item.initial_accepted is not None for item in selected)} | "
            f"{rate.numerator}/{rate.denominator} | {interval} | {audit.repair} | "
            f"{audit.unchanged_failure} | {audit.regression} | {audit.already_correct} | "
            f"{summary.tokens.total if summary.tokens.total is not None else 'unavailable'} | "
            f"{summary.capability_use.invocation_calls} | "
            f"{summary.wall_seconds.total if summary.wall_seconds.total is not None else 'unavailable'} | unavailable |"
        )
    lines.extend(
        [
            "",
            "## Paired acceptance tables",
            "",
            "| Contrast | Complete | Both failed | Left only | Right only | Both accepted | Difference | Exact p |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for pair in report.paired:
        lines.append(
            f"| {pair.contrast} | {pair.complete_binary_pairs}/{pair.planned_pairs} | "
            f"{pair.both_failed} | {pair.left_only_accepted} | {pair.right_only_accepted} | "
            f"{pair.both_accepted} | {pair.acceptance_difference if pair.acceptance_difference is not None else 'unavailable'} | "
            f"{pair.exact_p_value if pair.exact_p_value is not None else 'unavailable'} |"
        )
    lines.extend(["", "## Limits", ""] + [f"- {item}" for item in report.limitations])
    return "\n".join(lines) + "\n"


def emit_report(root: Path, output: Path) -> CloseoutReport:
    report = build_report(root)
    comparison._write_exclusive(output, report.model_dump(mode="json"))
    comparison._write_exclusive(output.with_suffix(".md"), render_report(report))
    return report


def _stack(value: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in value.split():
        name, separator, revision = item.partition("=")
        if not separator:
            raise argparse.ArgumentTypeError("stack revisions use name=sha")
        parsed[name] = revision
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--root", type=Path, required=True)
    plan.add_argument("--tasks", nargs="+", default=list(DEFAULT_TASKS))
    plan.add_argument("--stack-revisions", type=_stack, required=True)
    run = sub.add_parser("run")
    run.add_argument("--root", type=Path, required=True)
    run.add_argument("--execute", action="store_true")
    run.add_argument("--max-model-executions", type=int)
    run.add_argument("--retry-infrastructure", action="store_true")
    report = sub.add_parser("report")
    report.add_argument("--root", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    schemas = sub.add_parser("emit-schemas")
    schemas.add_argument("--manifest", type=Path, required=True)
    schemas.add_argument("--report", type=Path, required=True)
    schemas.add_argument("--feedback", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "plan":
        create_manifest(
            output=args.root,
            task_ids=args.tasks,
            stack_revisions=args.stack_revisions,
            source=os.environ,
        )
    elif args.command == "run":
        if not args.execute:
            raise CloseoutError("model execution requires --execute")
        print(
            json.dumps(
                run_experiment(
                    args.root,
                    source=os.environ,
                    max_model_executions=args.max_model_executions,
                    retry_infrastructure=args.retry_infrastructure,
                ),
                sort_keys=True,
            )
        )
    elif args.command == "report":
        emit_report(args.root, args.output)
    else:
        comparison._write_exclusive(args.manifest, CloseoutManifest.model_json_schema())
        comparison._write_exclusive(args.report, CloseoutReport.model_json_schema())
        comparison._write_exclusive(
            args.feedback, feedback.VerifierFeedback.model_json_schema()
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
