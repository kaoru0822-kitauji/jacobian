"""Repeatable paired symbolic-coordination observations and reports.

This module composes the PR2 host runner and PR3 trajectory normalizer.  It
does not alter benchmark tasks, model prompts, verifiers, or Jacobian policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from benchmarks.tooling import symbolic_coordination_codex as codex
from benchmarks.tooling import symbolic_coordination_trajectory as trajectory

SCHEMA_VERSION = "1"
DEFAULT_TASKS = (
    "symbolic-coordination-near-miss-01",
    "symbolic-coordination-grid-exhausted-01",
)
DEFAULT_REPETITIONS = 2
CONDITIONS = ("A", "B", "C")
ORDER_PERMUTATIONS: tuple[tuple[Condition, Condition, Condition], ...] = (
    ("A", "B", "C"),
    ("B", "C", "A"),
    ("C", "A", "B"),
    ("C", "B", "A"),
    ("A", "C", "B"),
    ("B", "A", "C"),
)

Condition = Literal["A", "B", "C"]
Availability = Literal["EXACT", "UNAVAILABLE"]
Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
HarborDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Revision = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]


class ComparisonError(RuntimeError):
    """A manifest, run, or report failed closed validation."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class BudgetValue(_StrictModel):
    availability: Literal["EXACT", "UNBOUNDED", "UNAVAILABLE"]
    value: int | float | None = Field(default=None, ge=0)
    unit: str

    @model_validator(mode="after")
    def _consistent(self) -> BudgetValue:
        if (self.availability == "EXACT") != (self.value is not None):
            raise ValueError("only exact budgets have a value")
        return self


class TaskBinding(_StrictModel):
    task_id: str
    family: str
    harbor_digest: HarborDigest
    public_file_hashes: dict[str, Digest]
    verifier_hashes: dict[str, Digest]


class RunUnit(_StrictModel):
    sequence: int = Field(ge=0)
    run_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]+$")
    task_id: str
    repetition: int = Field(ge=0)
    condition: Condition
    block_position: int = Field(ge=0, le=2)
    run_relpath: str = Field(pattern=r"^runs/[a-z0-9][a-z0-9-]+$")


class PreModelFailure(_StrictModel):
    schema_version: Literal["1"]
    failure_id: Digest
    run_id: str
    classification: Literal["PRE_MODEL_FAILURE"]
    exception_type: str
    message: str


class ExperimentManifest(_StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_extra={
            "$id": "https://jacobian.invalid/benchmarks/schemas/"
            "symbolic-coordination-experiment-v1.schema.json"
        },
    )

    schema_version: Literal["1"]
    experiment_id: Digest
    created_at: str
    evidence_class: Literal["host-local-workflow-observation"]
    causal_claim_authorized: Literal[False]
    source_revision: Revision
    source_branch: str
    stack_revisions: dict[str, Revision]
    dataset_id: Literal["symbolic-coordination-v1"]
    tasks: list[TaskBinding]
    repetitions: int = Field(ge=1)
    conditions: dict[Condition, dict[str, Any]]
    model: dict[str, Any]
    model_contract_digest: Digest
    reasoning_effort: str
    codex: dict[str, Any]
    auth: dict[str, Any]
    prompt_digests: dict[str, Digest]
    budgets: dict[str, BudgetValue]
    mcp: dict[str, Any]
    runtime: dict[str, Any]
    order_method: Literal["balanced-permutation-v1"]
    runs: list[RunUnit]

    @model_validator(mode="after")
    def _source_stack_binding(self) -> ExperimentManifest:
        if self.stack_revisions.get("pr4") != self.source_revision:
            raise ValueError("stack revision pr4 must equal the clean source revision")
        return self

    @model_validator(mode="after")
    def _manifest_invariants(self) -> ExperimentManifest:
        if set(self.conditions) != set(CONDITIONS):
            raise ValueError("manifest must bind exactly conditions A/B/C")
        task_ids = [task.task_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("duplicate task binding")
        run_ids = [run.run_id for run in self.runs]
        paths = [run.run_relpath for run in self.runs]
        sequences = [run.sequence for run in self.runs]
        if len(run_ids) != len(set(run_ids)) or len(paths) != len(set(paths)):
            raise ValueError("duplicate run identity")
        if sequences != list(range(len(self.runs))):
            raise ValueError("run sequences must be contiguous and ordered")
        expected = len(self.tasks) * self.repetitions * len(CONDITIONS)
        if len(self.runs) != expected:
            raise ValueError("manifest run matrix is incomplete")
        keys = Counter(
            (run.task_id, run.repetition, run.condition) for run in self.runs
        )
        if set(keys.values()) != {1} or len(keys) != expected:
            raise ValueError("each task/repetition/condition must occur exactly once")
        for task_id in task_ids:
            for repetition in range(self.repetitions):
                block = [
                    run
                    for run in self.runs
                    if run.task_id == task_id and run.repetition == repetition
                ]
                if sorted(run.block_position for run in block) != [0, 1, 2]:
                    raise ValueError("condition order block is malformed")
        return self


class Rate(_StrictModel):
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    value: float | None = Field(default=None, ge=0, le=1)
    wilson_low: float | None = Field(default=None, ge=0, le=1)
    wilson_high: float | None = Field(default=None, ge=0, le=1)


class ExactTotal(_StrictModel):
    availability: Availability
    exact_run_count: int = Field(ge=0)
    run_count: int = Field(ge=0)
    total: int | float | None = Field(default=None, ge=0)
    per_accepted: float | None = Field(default=None, ge=0)


class RunObservation(_StrictModel):
    run_id: str
    sequence: int = Field(ge=0)
    task_id: str
    task_family: str
    repetition: int = Field(ge=0)
    condition: Condition
    acquisition_status: Literal["OBSERVED", "PRE_MODEL_FAILURE", "MISSING"]
    infrastructure_status: Literal["COMPLETE", "INCOMPLETE", "UNAVAILABLE"]
    infrastructure_failures: list[str]
    mathematical_failure: bool | None
    verifier_available: bool
    accepted: bool | None
    reward: float | None = Field(default=None, ge=0, le=1)
    correctness: float | None = Field(default=None, ge=0, le=1)
    evidence_validity: float | None = Field(default=None, ge=0, le=1)
    scope_accuracy: float | None = Field(default=None, ge=0, le=1)
    assurance_calibration: float | None = Field(default=None, ge=0, le=1)
    input_binding: float | None = Field(default=None, ge=0, le=1)
    artifact_binding: float | None = Field(default=None, ge=0, le=1)
    false_certification: bool | None
    audit_classification: str
    revision_applied: bool | None
    total_tokens: int | None = Field(default=None, ge=0)
    wall_seconds: float | None = Field(default=None, ge=0)
    mcp_calls: int = Field(ge=0)
    shell_calls: int = Field(ge=0)
    discovery_calls: int = Field(ge=0)
    invocation_calls: int = Field(ge=0)
    reasoning_compliance: str
    protocol_violations: list[str]
    artifact_index_digest: Digest | None


class ConditionSummary(_StrictModel):
    condition: Condition
    planned_runs: int = Field(ge=0)
    observed_runs: int = Field(ge=0)
    infrastructure_completion: Rate
    infrastructure_failure: Rate
    verifier_availability: Rate
    acceptance: Rate
    mathematical_failure: Rate
    false_certification: Rate
    mean_scores: dict[str, float | None]
    audit_classifications: dict[str, int]
    capability_use: dict[str, int]
    reasoning_compliance: dict[str, int]
    tokens: ExactTotal
    wall_seconds: ExactTotal
    cost: ExactTotal


class PairedComparison(_StrictModel):
    contrast: Literal["A_TO_B", "B_TO_C"]
    left: Condition
    right: Condition
    planned_pairs: int = Field(ge=0)
    complete_binary_pairs: int = Field(ge=0)
    missing_pairs: int = Field(ge=0)
    both_failed: int = Field(ge=0)
    left_only_accepted: int = Field(ge=0)
    right_only_accepted: int = Field(ge=0)
    both_accepted: int = Field(ge=0)
    discordant_pairs: int = Field(ge=0)
    acceptance_difference: float | None = Field(default=None, ge=-1, le=1)
    exact_test: Literal["exact-paired-binomial-equivalent-to-mcnemar"]
    exact_p_value: float | None = Field(default=None, ge=0, le=1)
    exact_test_status: Literal["AVAILABLE", "NO_COMPLETE_PAIRS"]


class TaskReliability(_StrictModel):
    task_id: str
    task_family: str
    by_condition: dict[Condition, Rate]


class ComparisonReport(_StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_extra={
            "$id": "https://jacobian.invalid/benchmarks/schemas/"
            "symbolic-coordination-comparison-v1.schema.json"
        },
    )

    schema_version: Literal["1"]
    report_id: Digest
    manifest_id: Digest
    evidence_class: Literal["host-local-workflow-observation"]
    causal_claim_authorized: Literal[False]
    interpretation: Literal["descriptive-small-sample-pilot"]
    collection_status: Literal["COMPLETE", "PARTIAL"]
    planned_runs: int = Field(ge=0)
    observed_runs: int = Field(ge=0)
    pre_model_failures: int = Field(ge=0)
    missing_runs: int = Field(ge=0)
    records: list[RunObservation]
    conditions: list[ConditionSummary]
    paired: list[PairedComparison]
    task_reliability: list[TaskReliability]
    limitations: list[str]


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()


def _digest(value: object) -> str:
    raw = value if isinstance(value, bytes) else _canonical_bytes(value)
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ComparisonError(f"invalid JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise ComparisonError(f"expected JSON object: {path}")
    return value


def _write_exclusive(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(_canonical_bytes(value))
    except FileExistsError as exc:
        raise ComparisonError(f"refusing to overwrite {path}") from exc


def _load_pre_model_failure(path: Path) -> PreModelFailure:
    try:
        failure = PreModelFailure.model_validate(_read_json(path))
    except ValueError as exc:
        raise ComparisonError(f"invalid pre-model failure record: {path}") from exc
    body = failure.model_dump(mode="json")
    body.pop("failure_id")
    if failure.failure_id != _digest(body):
        raise ComparisonError(f"pre-model failure record drift: {path}")
    return failure


def _manifest_body(manifest: ExperimentManifest) -> dict[str, Any]:
    body = manifest.model_dump(mode="json")
    body.pop("experiment_id")
    return body


def load_manifest(root: Path) -> ExperimentManifest:
    path = root / "experiment-manifest.json"
    try:
        manifest = ExperimentManifest.model_validate(_read_json(path))
    except ValueError as exc:
        raise ComparisonError(f"invalid experiment manifest: {exc}") from exc
    if manifest.experiment_id != _digest(_manifest_body(manifest)):
        raise ComparisonError("experiment manifest digest drift")
    expected_preflight = manifest.runtime.get("preflight_report_digest")
    if isinstance(expected_preflight, str):
        preflight_path = root / "preflight.json"
        if (
            not preflight_path.is_file()
            or _digest(_read_json(preflight_path)) != expected_preflight
        ):
            raise ComparisonError("experiment preflight report drift")
    return manifest


def counterbalanced_runs(tasks: Sequence[str], repetitions: int) -> list[RunUnit]:
    if not tasks or len(set(tasks)) != len(tasks) or repetitions < 1:
        raise ComparisonError("tasks must be non-empty and unique; repetitions >= 1")
    runs: list[RunUnit] = []
    sequence = 0
    for repetition in range(repetitions):
        for task_index, task_id in enumerate(tasks):
            order = ORDER_PERMUTATIONS[
                (repetition * len(tasks) + task_index) % len(ORDER_PERMUTATIONS)
            ]
            for position, condition in enumerate(order):
                slug = f"r{repetition + 1}-{task_id}-{condition.lower()}"
                runs.append(
                    RunUnit(
                        sequence=sequence,
                        run_id=slug,
                        task_id=task_id,
                        repetition=repetition,
                        condition=condition,
                        block_position=position,
                        run_relpath=f"runs/{slug}",
                    )
                )
                sequence += 1
    return runs


def _task_family(contract: codex.TaskContract) -> str:
    value = _read_json(contract.path / "environment" / "input.json").get("family")
    if not isinstance(value, str) or not value:
        raise ComparisonError(f"task {contract.task_id} omitted family")
    return value


def create_manifest(
    *,
    output: Path,
    task_ids: Sequence[str],
    repetitions: int,
    stack_revisions: Mapping[str, str],
    source: Mapping[str, str],
) -> ExperimentManifest:
    if output.exists() or codex.ROOT in output.resolve().parents:
        raise ComparisonError("output must be a new directory outside the repository")
    preflight = codex.preflight(source)
    contracts = [codex._task_contract(task_id) for task_id in task_ids]
    tasks = [
        TaskBinding(
            task_id=item.task_id,
            family=_task_family(item),
            harbor_digest=item.harbor_digest,
            public_file_hashes=dict(item.public_hashes),
            verifier_hashes=dict(item.verifier_hashes),
        )
        for item in contracts
    ]
    snapshot = codex._snapshot_body(contracts[0], preflight)
    budgets = {
        "primary_wall_seconds": BudgetValue(
            availability="EXACT", value=codex.PRIMARY_TIMEOUT_SECONDS, unit="seconds"
        ),
        "audit_wall_seconds": BudgetValue(
            availability="EXACT", value=codex.AUDIT_TIMEOUT_SECONDS, unit="seconds"
        ),
        "tokens_per_stage": BudgetValue(
            availability="EXACT", value=codex.MAX_TOTAL_TOKENS, unit="tokens"
        ),
        "tool_calls_per_stage": BudgetValue(
            availability="UNBOUNDED", value=None, unit="calls"
        ),
        "cost": BudgetValue(availability="UNAVAILABLE", value=None, unit="USD"),
    }
    body = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "evidence_class": "host-local-workflow-observation",
        "causal_claim_authorized": False,
        "source_revision": preflight.source_revision,
        "source_branch": preflight.branch,
        "stack_revisions": dict(sorted(stack_revisions.items())),
        "dataset_id": codex.DATASET_ID,
        "tasks": [item.model_dump(mode="json") for item in tasks],
        "repetitions": repetitions,
        "conditions": snapshot["conditions"],
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
        },
        "budgets": {
            key: value.model_dump(mode="json") for key, value in budgets.items()
        },
        "mcp": {
            "executable_digest": codex._digest_file(preflight.mcp),
            "policy_profile": "COMPUTE_VERIFY_NO_RETRIEVAL",
            "conditions": ["B", "C"],
            "audit_stage_enabled": False,
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "harbor_version": codex.HARBOR_VERSION,
            "uv_lock_digest": codex._digest_file(codex.ROOT / "uv.lock"),
            "pilot_manifest_digest": codex._digest_file(
                codex.DATASET / "pilot-manifest.json"
            ),
            "preflight_report_digest": _digest(preflight.report),
            "sampling_seed": None,
            "sampling_temperature": None,
            "sampling_source": "codex-cli-chatgpt-defaults-no-cli-overrides",
        },
        "order_method": "balanced-permutation-v1",
        "runs": [
            item.model_dump(mode="json")
            for item in counterbalanced_runs(task_ids, repetitions)
        ],
    }
    manifest = ExperimentManifest.model_validate(
        {**body, "experiment_id": _digest(body)}
    )
    output.mkdir(parents=True)
    manifest_path = output / "experiment-manifest.json"
    _write_exclusive(manifest_path, manifest.model_dump(mode="json"))
    manifest_path.chmod(0o444)
    _write_exclusive(output / "preflight.json", preflight.report)
    return manifest


def _validate_current_contract(manifest: ExperimentManifest) -> None:
    revision, branch = codex._require_clean_source()
    if revision != manifest.source_revision or branch != manifest.source_branch:
        raise ComparisonError("current clean source does not match manifest")
    if manifest.model.get("slug") != codex.DEFAULT_MODEL:
        raise ComparisonError("model selection drift")
    if manifest.reasoning_effort != codex.DEFAULT_REASONING_EFFORT:
        raise ComparisonError("reasoning effort drift")
    prompt_digests = {
        "primary": codex._digest_bytes(codex.PRIMARY_PROMPT.encode()),
        "audit": codex._digest_bytes(codex.AUDIT_PROMPT.encode()),
    }
    if prompt_digests != manifest.prompt_digests:
        raise ComparisonError("prompt drift")
    bound = {task.task_id: task for task in manifest.tasks}
    for task_id, expected in bound.items():
        actual = codex._task_contract(task_id)
        if (
            actual.harbor_digest != expected.harbor_digest
            or dict(actual.public_hashes) != expected.public_file_hashes
            or dict(actual.verifier_hashes) != expected.verifier_hashes
        ):
            raise ComparisonError(f"task contract drift: {task_id}")


def _record_matches_unit(
    root: Path, manifest: ExperimentManifest, unit: RunUnit
) -> trajectory.RunTelemetry:
    try:
        records = trajectory.analyze_run(root)
    except (OSError, ValueError, trajectory.TrajectoryTelemetryError) as exc:
        raise ComparisonError(
            f"corrupt run artifacts for {unit.run_id}: {exc}"
        ) from exc
    if len(records) != 1:
        raise ComparisonError(f"run {unit.run_id} must contain exactly one condition")
    record = records[0]
    if (
        record.task_id != unit.task_id
        or record.condition != unit.condition
        or record.source_revision != manifest.source_revision
        or record.model != manifest.model.get("slug")
        or record.reasoning_effort != manifest.reasoning_effort
    ):
        raise ComparisonError(f"run identity drift: {unit.run_id}")
    snapshot = _read_json(root / "runtime-snapshot.json")
    task = next(item for item in manifest.tasks if item.task_id == unit.task_id)
    prompts = snapshot.get("prompts")
    snapshot_task = snapshot.get("task")
    if (
        not isinstance(prompts, dict)
        or {
            "primary": prompts.get("primary_digest"),
            "audit": prompts.get("audit_digest"),
        }
        != manifest.prompt_digests
    ):
        raise ComparisonError(f"run prompt binding drift: {unit.run_id}")
    if (
        not isinstance(snapshot_task, dict)
        or snapshot_task.get("harbor_digest") != task.harbor_digest
    ):
        raise ComparisonError(f"run task digest drift: {unit.run_id}")
    return record


def _resume_decision(
    root: Path,
    manifest: ExperimentManifest,
    unit: RunUnit,
    *,
    retry_infrastructure: bool,
    execution_available: bool,
) -> tuple[trajectory.RunTelemetry | None, bool, bool]:
    """Return (existing record, execute now, skipped pre-model failure)."""

    run_root = root / unit.run_relpath
    failure_path = root / "pre-model-failures" / f"{unit.run_id}.json"
    if run_root.exists():
        record = _record_matches_unit(run_root, manifest, unit)
        should_retry = (
            record.infrastructure_status == "INCOMPLETE"
            and retry_infrastructure
            and execution_available
        )
        if not should_retry:
            return record, False, False
        history = root / "retry-history" / unit.run_id
        history.mkdir(parents=True, exist_ok=True)
        attempt = len(list(history.glob("run-attempt-*"))) + 1
        run_root.rename(history / f"run-attempt-{attempt:03d}")
        return None, True, False
    if failure_path.exists():
        _load_pre_model_failure(failure_path)
        should_retry = retry_infrastructure and execution_available
        if not should_retry:
            return None, False, True
        history = root / "retry-history" / unit.run_id
        history.mkdir(parents=True, exist_ok=True)
        attempt = len(list(history.glob("pre-model-attempt-*.json"))) + 1
        failure_path.rename(history / f"pre-model-attempt-{attempt:03d}.json")
        return None, True, False
    return None, execution_available, False


def run_experiment(
    root: Path,
    *,
    source: Mapping[str, str],
    max_model_executions: int | None,
    retry_infrastructure: bool = False,
) -> dict[str, int]:
    manifest = load_manifest(root)
    _validate_current_contract(manifest)
    complete = 0
    executed = 0
    incomplete = 0
    for unit in manifest.runs:
        run_root = root / unit.run_relpath
        execution_available = (
            max_model_executions is None or executed < max_model_executions
        )
        record, should_execute, skipped_failure = _resume_decision(
            root,
            manifest,
            unit,
            retry_infrastructure=retry_infrastructure,
            execution_available=execution_available,
        )
        if record is not None:
            complete += 1
            incomplete += record.infrastructure_status == "INCOMPLETE"
            continue
        if skipped_failure:
            incomplete += 1
            continue
        if not should_execute:
            break
        try:
            codex.execute(
                task_id=unit.task_id,
                output_path=run_root,
                conditions=[unit.condition],
                dry_run=False,
                source=source,
            )
            record = _record_matches_unit(run_root, manifest, unit)
        except Exception as exc:
            # A missing run root means the harness failed before model execution.
            # Preserve the exact failure without inventing a mathematical result.
            if run_root.exists():
                raise
            body = {
                "schema_version": "1",
                "run_id": unit.run_id,
                "classification": "PRE_MODEL_FAILURE",
                "exception_type": type(exc).__name__,
                "message": str(exc),
            }
            failure = PreModelFailure.model_validate(
                {**body, "failure_id": _digest(body)}
            )
            path = root / "pre-model-failures" / f"{unit.run_id}.json"
            _write_exclusive(path, failure.model_dump(mode="json"))
            raise ComparisonError(
                f"pre-model failure recorded for {unit.run_id}: {exc}"
            ) from exc
        executed += 1
        complete += 1
        incomplete += record.infrastructure_status == "INCOMPLETE"
    return {
        "observed": complete,
        "executed": executed,
        "infrastructure_incomplete": incomplete,
    }


def _wilson(successes: int, denominator: int) -> Rate:
    if denominator == 0:
        return Rate(
            numerator=successes,
            denominator=0,
            value=None,
            wilson_low=None,
            wilson_high=None,
        )
    z = 1.959963984540054
    p = successes / denominator
    z2 = z * z
    scale = 1 + z2 / denominator
    center = (p + z2 / (2 * denominator)) / scale
    spread = z * math.sqrt((p * (1 - p) + z2 / (4 * denominator)) / denominator) / scale
    return Rate(
        numerator=successes,
        denominator=denominator,
        value=p,
        wilson_low=max(0.0, center - spread),
        wilson_high=min(1.0, center + spread),
    )


def _exact_p_value(left_only: int, right_only: int) -> float:
    discordant = left_only + right_only
    if discordant == 0:
        return 1.0
    tail = sum(math.comb(discordant, k) for k in range(min(left_only, right_only) + 1))
    return float(min(1.0, 2.0 * tail / (2**discordant)))


def _exact_tokens(record: trajectory.RunTelemetry) -> int | None:
    primary = record.usage.primary
    if primary.availability != "EXACT" or primary.total_tokens is None:
        return None
    if record.condition != "C":
        return primary.total_tokens
    audit = record.usage.audit
    if audit is None or audit.availability != "EXACT" or audit.total_tokens is None:
        return None
    return primary.total_tokens + audit.total_tokens


def _observation(
    manifest: ExperimentManifest,
    unit: RunUnit,
    record: trajectory.RunTelemetry | None,
    acquisition: Literal["OBSERVED", "PRE_MODEL_FAILURE", "MISSING"],
    failures: Sequence[str] = (),
) -> RunObservation:
    task = next(item for item in manifest.tasks if item.task_id == unit.task_id)
    if record is None:
        return RunObservation(
            run_id=unit.run_id,
            sequence=unit.sequence,
            task_id=unit.task_id,
            task_family=task.family,
            repetition=unit.repetition,
            condition=unit.condition,
            acquisition_status=acquisition,
            infrastructure_status="UNAVAILABLE",
            infrastructure_failures=list(failures),
            mathematical_failure=None,
            verifier_available=False,
            accepted=None,
            reward=None,
            correctness=None,
            evidence_validity=None,
            scope_accuracy=None,
            assurance_calibration=None,
            input_binding=None,
            artifact_binding=None,
            false_certification=None,
            audit_classification="UNAVAILABLE",
            revision_applied=None,
            total_tokens=None,
            wall_seconds=None,
            mcp_calls=0,
            shell_calls=0,
            discovery_calls=0,
            invocation_calls=0,
            reasoning_compliance="UNAVAILABLE",
            protocol_violations=[],
            artifact_index_digest=None,
        )
    verifier = record.audit.final_verifier
    accepted = verifier.reward == 1.0 if verifier is not None else None
    return RunObservation(
        run_id=unit.run_id,
        sequence=unit.sequence,
        task_id=unit.task_id,
        task_family=record.task_family,
        repetition=unit.repetition,
        condition=unit.condition,
        acquisition_status="OBSERVED",
        infrastructure_status=record.infrastructure_status,
        infrastructure_failures=record.infrastructure_failures,
        mathematical_failure=(not accepted)
        if record.infrastructure_status == "COMPLETE" and accepted is not None
        else None,
        verifier_available=verifier is not None,
        accepted=accepted,
        reward=verifier.reward if verifier else None,
        correctness=verifier.correctness if verifier else None,
        evidence_validity=verifier.evidence_validity if verifier else None,
        scope_accuracy=verifier.scope_accuracy if verifier else None,
        assurance_calibration=verifier.assurance_calibration if verifier else None,
        input_binding=verifier.input_binding if verifier else None,
        artifact_binding=verifier.artifact_binding if verifier else None,
        false_certification=verifier.false_certification if verifier else None,
        audit_classification=record.audit.classification,
        revision_applied=record.audit.revision_applied,
        total_tokens=_exact_tokens(record),
        wall_seconds=record.wall_time.total_seconds,
        mcp_calls=record.calls.mcp_calls,
        shell_calls=record.calls.shell_calls,
        discovery_calls=record.calls.discovery_calls,
        invocation_calls=record.calls.invocation_calls,
        reasoning_compliance=record.reasoning_protocol.compliance,
        protocol_violations=record.classification.protocol_violations,
        artifact_index_digest=record.source_artifact_index_digest,
    )


def _exact_total(values: Sequence[int | float | None], accepted: int) -> ExactTotal:
    exact = [value for value in values if value is not None]
    complete = len(exact) == len(values)
    total = sum(exact) if complete else None
    return ExactTotal(
        availability="EXACT" if complete else "UNAVAILABLE",
        exact_run_count=len(exact),
        run_count=len(values),
        total=total,
        per_accepted=(float(total) / accepted)
        if total is not None and accepted
        else None,
    )


def _mean(records: Sequence[RunObservation], name: str) -> float | None:
    values = [
        getattr(record, name) for record in records if getattr(record, name) is not None
    ]
    return sum(values) / len(values) if values else None


def _condition_summary(
    condition: Condition, records: Sequence[RunObservation]
) -> ConditionSummary:
    selected = [record for record in records if record.condition == condition]
    observed = [
        record for record in selected if record.acquisition_status == "OBSERVED"
    ]
    infra = [
        record for record in observed if record.infrastructure_status == "COMPLETE"
    ]
    verified = [record for record in observed if record.verifier_available]
    binary = [record for record in observed if record.accepted is not None]
    accepted = sum(record.accepted is True for record in binary)
    math = [record for record in observed if record.mathematical_failure is not None]
    false = [record for record in verified if record.false_certification is not None]
    infrastructure_failures = sum(
        record.acquisition_status == "PRE_MODEL_FAILURE"
        or (
            record.acquisition_status == "OBSERVED"
            and record.infrastructure_status == "INCOMPLETE"
        )
        for record in selected
    )
    return ConditionSummary(
        condition=condition,
        planned_runs=len(selected),
        observed_runs=len(observed),
        infrastructure_completion=_wilson(len(infra), len(selected)),
        infrastructure_failure=_wilson(infrastructure_failures, len(selected)),
        verifier_availability=_wilson(len(verified), len(selected)),
        acceptance=_wilson(accepted, len(binary)),
        mathematical_failure=_wilson(
            sum(item.mathematical_failure is True for item in math), len(math)
        ),
        false_certification=_wilson(
            sum(item.false_certification is True for item in false), len(false)
        ),
        mean_scores={
            name: _mean(verified, name)
            for name in (
                "correctness",
                "evidence_validity",
                "scope_accuracy",
                "assurance_calibration",
                "input_binding",
                "artifact_binding",
                "reward",
            )
        },
        audit_classifications=dict(
            sorted(Counter(item.audit_classification for item in observed).items())
        ),
        capability_use={
            "mcp_calls": sum(item.mcp_calls for item in observed),
            "discovery_calls": sum(item.discovery_calls for item in observed),
            "invocation_calls": sum(item.invocation_calls for item in observed),
            "runs_with_invocation": sum(item.invocation_calls > 0 for item in observed),
        },
        reasoning_compliance=dict(
            sorted(Counter(item.reasoning_compliance for item in observed).items())
        ),
        tokens=_exact_total([item.total_tokens for item in observed], accepted),
        wall_seconds=_exact_total([item.wall_seconds for item in observed], accepted),
        cost=ExactTotal(
            availability="UNAVAILABLE",
            exact_run_count=0,
            run_count=len(observed),
            total=None,
            per_accepted=None,
        ),
    )


def _paired(
    records: Sequence[RunObservation], left: Condition, right: Condition
) -> PairedComparison:
    indexed = {
        (item.task_id, item.repetition, item.condition): item for item in records
    }
    keys = sorted({(item.task_id, item.repetition) for item in records})
    counts = Counter[str]()
    for task_id, repetition in keys:
        a = indexed[(task_id, repetition, left)].accepted
        b = indexed[(task_id, repetition, right)].accepted
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
    complete = len(keys) - counts["missing"]
    difference = (
        (counts["right_only"] - counts["left_only"]) / complete if complete else None
    )
    return PairedComparison(
        contrast="A_TO_B" if (left, right) == ("A", "B") else "B_TO_C",
        left=left,
        right=right,
        planned_pairs=len(keys),
        complete_binary_pairs=complete,
        missing_pairs=counts["missing"],
        both_failed=counts["both_failed"],
        left_only_accepted=counts["left_only"],
        right_only_accepted=counts["right_only"],
        both_accepted=counts["both_accepted"],
        discordant_pairs=counts["left_only"] + counts["right_only"],
        acceptance_difference=difference,
        exact_test="exact-paired-binomial-equivalent-to-mcnemar",
        exact_p_value=_exact_p_value(counts["left_only"], counts["right_only"])
        if complete
        else None,
        exact_test_status="AVAILABLE" if complete else "NO_COMPLETE_PAIRS",
    )


def build_report(root: Path) -> ComparisonReport:
    manifest = load_manifest(root)
    records: list[RunObservation] = []
    for unit in manifest.runs:
        run_root = root / unit.run_relpath
        failure_path = root / "pre-model-failures" / f"{unit.run_id}.json"
        if run_root.exists():
            record = _record_matches_unit(run_root, manifest, unit)
            records.append(_observation(manifest, unit, record, "OBSERVED"))
        elif failure_path.exists():
            failure = _load_pre_model_failure(failure_path)
            records.append(
                _observation(
                    manifest,
                    unit,
                    None,
                    "PRE_MODEL_FAILURE",
                    [failure.message],
                )
            )
        else:
            records.append(_observation(manifest, unit, None, "MISSING"))
    conditions = [_condition_summary(condition, records) for condition in CONDITIONS]
    reliability = []
    for task in manifest.tasks:
        selected = [item for item in records if item.task_id == task.task_id]
        by_condition: dict[Condition, Rate] = {}
        for condition in CONDITIONS:
            binary = [
                item
                for item in selected
                if item.condition == condition and item.accepted is not None
            ]
            by_condition[condition] = _wilson(
                sum(item.accepted is True for item in binary), len(binary)
            )
        reliability.append(
            TaskReliability(
                task_id=task.task_id, task_family=task.family, by_condition=by_condition
            )
        )
    body = {
        "schema_version": "1",
        "manifest_id": manifest.experiment_id,
        "evidence_class": "host-local-workflow-observation",
        "causal_claim_authorized": False,
        "interpretation": "descriptive-small-sample-pilot",
        "collection_status": "COMPLETE"
        if all(item.acquisition_status == "OBSERVED" for item in records)
        else "PARTIAL",
        "planned_runs": len(records),
        "observed_runs": sum(item.acquisition_status == "OBSERVED" for item in records),
        "pre_model_failures": sum(
            item.acquisition_status == "PRE_MODEL_FAILURE" for item in records
        ),
        "missing_runs": sum(item.acquisition_status == "MISSING" for item in records),
        "records": [item.model_dump(mode="json") for item in records],
        "conditions": [item.model_dump(mode="json") for item in conditions],
        "paired": [
            _paired(records, "A", "B").model_dump(mode="json"),
            _paired(records, "B", "C").model_dump(mode="json"),
        ],
        "task_reliability": [item.model_dump(mode="json") for item in reliability],
        "limitations": [
            "This small nondeterministic pilot is descriptive and does not identify causal lift.",
            "ChatGPT-authenticated Codex does not expose monetary cost; cost fields remain unavailable.",
            "Exact paired tests describe discordance and are not corrected for multiple comparisons.",
            "Unavailable telemetry is never imputed as zero, failure, or success.",
        ],
    }
    return ComparisonReport.model_validate({**body, "report_id": _digest(body)})


def render_report(report: ComparisonReport) -> str:
    lines = [
        "# Symbolic coordination repeated comparison",
        "",
        f"Collection: **{report.collection_status}**; observed {report.observed_runs}/{report.planned_runs} planned runs.",
        "",
        "This is a descriptive small-sample host-local workflow observation. It does not authorize a causal claim.",
        "",
        "## Conditions",
        "",
        "| Condition | Infra complete | Accepted | False certification | Tokens | Wall seconds |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in report.conditions:

        def rate(value: Rate) -> str:
            return (
                "unavailable"
                if value.value is None
                else f"{value.numerator}/{value.denominator} ({value.value:.3f})"
            )

        lines.append(
            f"| {row.condition} | {rate(row.infrastructure_completion)} | {rate(row.acceptance)} | "
            f"{rate(row.false_certification)} | {row.tokens.total if row.tokens.total is not None else 'unavailable'} | "
            f"{row.wall_seconds.total if row.wall_seconds.total is not None else 'unavailable'} |"
        )
    lines.extend(
        [
            "",
            "## Paired acceptance",
            "",
            "| Contrast | Complete | Left only | Right only | Difference | Exact p |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for pair in report.paired:
        diff = (
            "unavailable"
            if pair.acceptance_difference is None
            else f"{pair.acceptance_difference:.3f}"
        )
        p = "unavailable" if pair.exact_p_value is None else f"{pair.exact_p_value:.6f}"
        lines.append(
            f"| {pair.contrast} | {pair.complete_binary_pairs}/{pair.planned_pairs} | {pair.left_only_accepted} | {pair.right_only_accepted} | {diff} | {p} |"
        )
    lines.extend(
        ["", "## Limitations", ""] + [f"- {item}" for item in report.limitations]
    )
    return "\n".join(lines) + "\n"


def emit_report(root: Path, output: Path, markdown: Path | None) -> ComparisonReport:
    report = build_report(root)
    _write_exclusive(output, report.model_dump(mode="json"))
    if markdown is not None:
        markdown.parent.mkdir(parents=True, exist_ok=True)
        try:
            with markdown.open("x", encoding="utf-8", newline="") as stream:
                stream.write(render_report(report))
        except FileExistsError as exc:
            raise ComparisonError(f"refusing to overwrite {markdown}") from exc
    return report


def _stack(values: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        name, separator, revision = value.partition("=")
        if (
            not separator
            or not name
            or len(revision) != 40
            or any(ch not in "0123456789abcdef" for ch in revision)
        ):
            raise ComparisonError("stack revisions must be NAME=40-lowercase-hex-SHA")
        if name in result:
            raise ComparisonError(f"duplicate stack revision: {name}")
        result[name] = revision
    if not result:
        raise ComparisonError("at least one --stack-revision is required")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--tasks", nargs="+", default=list(DEFAULT_TASKS))
    plan.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS)
    plan.add_argument("--stack-revision", action="append", default=[])
    run = sub.add_parser("run")
    run.add_argument("--root", type=Path, required=True)
    run.add_argument("--max-model-executions", type=int)
    run.add_argument("--retry-infrastructure", action="store_true")
    report = sub.add_parser("report")
    report.add_argument("--root", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    report.add_argument("--markdown-output", type=Path)
    schemas = sub.add_parser("schemas")
    schemas.add_argument("--experiment", type=Path, required=True)
    schemas.add_argument("--comparison", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "plan":
            manifest = create_manifest(
                output=args.output,
                task_ids=args.tasks,
                repetitions=args.repetitions,
                stack_revisions=_stack(args.stack_revision),
                source=os.environ,
            )
            print(
                json.dumps(
                    {
                        "experiment_id": manifest.experiment_id,
                        "planned_runs": len(manifest.runs),
                    },
                    sort_keys=True,
                )
            )
        elif args.command == "run":
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
            report = emit_report(args.root, args.output, args.markdown_output)
            print(render_report(report), end="")
        else:
            _write_exclusive(args.experiment, ExperimentManifest.model_json_schema())
            _write_exclusive(args.comparison, ComparisonReport.model_json_schema())
    except (ComparisonError, codex.HarnessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
