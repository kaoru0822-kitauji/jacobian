"""Deterministic trajectory telemetry for symbolic-coordination Codex runs.

The analyzer consumes only preserved host-run artifacts.  It verifies their
content-addressed index before parsing them and emits a closed, versioned
record.  Mathematical scores remain the clean-room verifier's values; workflow
classifications use typed events and explicit task-family rules only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from jacobian.eval.telemetry import parse_agent_transcript

SCHEMA_VERSION = "1"
Condition = Literal["A", "B", "C", "D"]
AggregateCondition = Literal["A", "B", "C", "D", "ALL"]
InfrastructureStatus = Literal["COMPLETE", "INCOMPLETE"]
CONDITIONS: tuple[Condition, ...] = ("A", "B", "C", "D")
TASK_FAMILY_DOMAINS: Mapping[str, frozenset[str]] = {
    "valid-two-sided-inverse": frozenset({"polynomial"}),
    "perturbed-near-miss": frozenset({"polynomial"}),
    "one-direction-only-evidence": frozenset({"polynomial"}),
    "constant-nonzero-jacobian": frozenset({"polynomial"}),
    "bounded-collision-scope": frozenset({"polynomial"}),
    "semantic-equivalence": frozenset({"polynomial"}),
}
PRODUCER_RULES: Mapping[str, tuple[str, tuple[str, ...]]] = {
    "polynomial.map.inverse.candidate_synthesize": (
        "candidate_inverse_map",
        ("polynomial.map.inverse.verify",),
    ),
    "polynomial.map.collision_witness": (
        "witness_uri",
        ("polynomial.map.collision.verify",),
    ),
    "polynomial.map.collision.search": (
        "witness_uri",
        ("polynomial.map.collision.verify",),
    ),
    "polynomial.map.compute_jacobian": (
        "jacobian_uri",
        ("polynomial.map.keller_condition.verify",),
    ),
}
PRODUCER_IDS = frozenset(PRODUCER_RULES)
CHECKER_IDS = frozenset(
    checker for _, checkers in PRODUCER_RULES.values() for checker in checkers
)
PARAMETER_ERROR_CODES = frozenset(
    {
        "INVALID_ARGUMENT",
        "INVALID_CONSTRAINT_RANGE",
        "INVALID_PARAMS",
        "INVALID_REQUEST",
        "SCHEMA_VALIDATION",
        "invalid_params",
        -32602,
    }
)
STALE_BINDING_CODES = frozenset(
    {
        "MISBOUND_POLYNOMIAL_EVALUATION_ARTIFACT",
        "POLYNOMIAL_EVALUATION_ARTIFACT_NOT_FOUND",
        "POLYNOMIAL_MAP_ARTIFACT_NOT_FOUND",
    }
)
SUBSTITUTION_CODES = frozenset(
    {
        "INCOMPATIBLE_POLYNOMIAL_EVALUATION_ARTIFACT",
        "INCOMPATIBLE_POLYNOMIAL_MAP_ARTIFACT",
    }
)
NONCONCLUSIVE_STATUSES = frozenset(
    {"TIMEOUT", "CANCELLED", "ERROR", "INCOMPLETE", "UNKNOWN"}
)
REASONING_PHASES = ("PLAN", "BEFORE_TOOL", "AFTER_TOOL", "FINAL")
AuditClassification = Literal[
    "NOT_APPLICABLE",
    "REPAIR",
    "UNCHANGED_FAILURE",
    "REGRESSION",
    "ALREADY_CORRECT",
    "INCOMPLETE",
]


class TrajectoryTelemetryError(RuntimeError):
    """Raw run artifacts cannot support a trustworthy telemetry record."""


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _ArtifactEntry(_StrictModel):
    path: str
    bytes: int = Field(ge=0)
    digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class _ArtifactIndex(_StrictModel):
    schema_version: Literal["1"]
    files: list[_ArtifactEntry]


class TokenUsage(_StrictModel):
    availability: Literal["EXACT", "UNAVAILABLE"]
    input_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    cache_write_input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    reasoning_output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class StageUsage(_StrictModel):
    primary: TokenUsage
    audit: TokenUsage | None


class WallTime(_StrictModel):
    primary_seconds: float | None = Field(default=None, ge=0)
    audit_seconds: float | None = Field(default=None, ge=0)
    total_seconds: float | None = Field(default=None, ge=0)


class CapabilityCall(_StrictModel):
    sequence: int = Field(ge=0)
    capability_id: str | None
    argument_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    schema_valid: bool
    executable: bool
    failed: bool
    repeated: bool
    task_relevant: bool | None
    execution_status: str | None
    output_status: str | None
    completeness_status: str | None
    produced_kind: str | None
    produced: bool
    applicable_checker_ids: list[str]
    checker_followed: bool | None
    artifact_uris: list[str]
    error_codes: list[str]


class CallMetrics(_StrictModel):
    mcp_calls: int = Field(ge=0)
    shell_calls: int = Field(ge=0)
    discovery_calls: int = Field(ge=0)
    invocation_calls: int = Field(ge=0)
    schema_valid_calls: int = Field(ge=0)
    executable_calls: int = Field(ge=0)
    failed_calls: int = Field(ge=0)
    repeated_calls: int = Field(ge=0)
    task_irrelevant_calls: int = Field(ge=0)
    producer_calls: int = Field(ge=0)
    checker_calls: int = Field(ge=0)
    candidate_or_witness_productions: int = Field(ge=0)
    missing_applicable_checker: int = Field(ge=0)
    recovered_calls: int = Field(ge=0)


class SearchOutcomeMetrics(_StrictModel):
    timeout_count: int = Field(ge=0)
    cancellation_count: int = Field(ge=0)
    incomplete_count: int = Field(ge=0)
    bounded_exhaustion_count: int = Field(ge=0)
    unresolved_nonconclusive_count: int = Field(ge=0)
    final_claim_improperly_escalates: bool


class ArtifactFlow(_StrictModel):
    created_uris: list[str]
    handoff_count: int = Field(ge=0)
    reused_uri_count: int = Field(ge=0)
    stale_binding_failure_count: int = Field(ge=0)
    substitution_failure_count: int = Field(ge=0)
    final_input_binding_valid: bool | None
    final_artifact_binding_valid: bool | None


class ReasoningProtocol(_StrictModel):
    mode: Literal["OFF", "REQUIRED"]
    compliance: Literal["NOT_APPLICABLE", "COMPLETE", "INCOMPLETE"]
    plan_count: int = Field(ge=0)
    before_tool_count: int = Field(ge=0)
    after_tool_count: int = Field(ge=0)
    final_count: int = Field(ge=0)
    log_status: Literal["NOT_APPLICABLE", "EMPTY", "EXPORTED"]
    log_entries: int = Field(ge=0)
    log_bytes: int = Field(ge=0)
    token_overhead_availability: Literal["EXACT", "UNAVAILABLE"]
    token_overhead_tokens: int | None = Field(default=None, ge=0)


class SubmissionState(_StrictModel):
    present: bool
    schema_valid: bool | None
    digest: str | None
    conclusion: str | None
    verdict: str | None
    claimed_assurance: str | None
    scope: str | None
    completeness: str | None


class VerifierScores(_StrictModel):
    execution_status: str
    mathematical_observation: str
    correctness: float = Field(ge=0, le=1)
    evidence_validity: float = Field(ge=0, le=1)
    scope_accuracy: float = Field(ge=0, le=1)
    assurance_calibration: float = Field(ge=0, le=1)
    input_binding: float = Field(ge=0, le=1)
    artifact_binding: float = Field(ge=0, le=1)
    protocol_compliance: float = Field(ge=0, le=1)
    false_certification: bool
    reward: float = Field(ge=0, le=1)


class AuditComparison(_StrictModel):
    revision_applied: bool | None
    classification: AuditClassification
    initial_submission: SubmissionState
    final_submission: SubmissionState
    initial_verifier: VerifierScores | None
    final_verifier: VerifierScores | None


class TrajectoryClassification(_StrictModel):
    protocol_violations: list[str]
    successful_recovery: bool
    audit_outcome: str


class RunTelemetry(_StrictModel):
    telemetry_schema_version: Literal["1"]
    source_artifact_index_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    snapshot_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    task_id: str
    task_family: str
    condition: Condition
    model: str
    reasoning_effort: str
    infrastructure_status: Literal["COMPLETE", "INCOMPLETE"]
    infrastructure_failures: list[str]
    usage: StageUsage
    wall_time: WallTime
    calls: CallMetrics
    capability_calls: list[CapabilityCall]
    search_outcomes: SearchOutcomeMetrics
    artifact_flow: ArtifactFlow
    reasoning_protocol: ReasoningProtocol
    audit: AuditComparison
    classification: TrajectoryClassification


class AggregateRow(_StrictModel):
    task_id: str
    condition: AggregateCondition
    run_count: int = Field(ge=0)
    infrastructure_complete: int = Field(ge=0)
    correctness_mean: float | None = Field(default=None, ge=0, le=1)
    evidence_validity_mean: float | None = Field(default=None, ge=0, le=1)
    scope_accuracy_mean: float | None = Field(default=None, ge=0, le=1)
    assurance_calibration_mean: float | None = Field(default=None, ge=0, le=1)
    input_binding_mean: float | None = Field(default=None, ge=0, le=1)
    artifact_binding_mean: float | None = Field(default=None, ge=0, le=1)
    protocol_compliance_mean: float | None = Field(default=None, ge=0, le=1)
    reward_mean: float | None = Field(default=None, ge=0, le=1)
    verifier_result_count: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    false_certification_count: int = Field(ge=0)
    exact_token_run_count: int = Field(ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    exact_wall_run_count: int = Field(ge=0)
    wall_seconds: float | None = Field(default=None, ge=0)
    mcp_calls: int = Field(ge=0)
    shell_calls: int = Field(ge=0)
    discovery_calls: int = Field(ge=0)
    invocation_calls: int = Field(ge=0)
    schema_valid_calls: int = Field(ge=0)
    executable_calls: int = Field(ge=0)
    failed_calls: int = Field(ge=0)
    repeated_calls: int = Field(ge=0)
    task_irrelevant_calls: int = Field(ge=0)
    producer_calls: int = Field(ge=0)
    checker_calls: int = Field(ge=0)
    candidate_or_witness_productions: int = Field(ge=0)
    missing_applicable_checker: int = Field(ge=0)
    recovered_calls: int = Field(ge=0)
    timeout_count: int = Field(ge=0)
    cancellation_count: int = Field(ge=0)
    incomplete_search_count: int = Field(ge=0)
    bounded_exhaustion_count: int = Field(ge=0)
    unresolved_nonconclusive_count: int = Field(ge=0)
    improper_escalation_run_count: int = Field(ge=0)
    created_artifact_uri_count: int = Field(ge=0)
    artifact_handoff_count: int = Field(ge=0)
    reused_artifact_uri_count: int = Field(ge=0)
    stale_binding_failure_count: int = Field(ge=0)
    substitution_failure_count: int = Field(ge=0)
    reasoning_required_run_count: int = Field(ge=0)
    reasoning_complete_run_count: int = Field(ge=0)
    reasoning_incomplete_run_count: int = Field(ge=0)
    reasoning_log_entries: int = Field(ge=0)
    reasoning_log_bytes: int = Field(ge=0)
    exact_reasoning_overhead_run_count: int = Field(ge=0)
    reasoning_overhead_tokens: int | None = Field(default=None, ge=0)
    protocol_violation_count: int = Field(ge=0)
    audit_classifications: dict[str, int]


class AggregateTables(_StrictModel):
    per_task: list[AggregateRow]
    overall: list[AggregateRow]


class TelemetryBundle(_StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_extra={
            "$id": "https://jacobian.invalid/benchmarks/schemas/symbolic-coordination-trajectory-v1.schema.json"
        },
    )

    schema_version: Literal["1"]
    evidence_class: Literal["host-local-workflow-observation"]
    causal_claim_authorized: Literal[False]
    records: list[RunTelemetry]
    aggregates: AggregateTables


@dataclass(frozen=True, slots=True)
class _ConditionIdentity:
    snapshot_id: str
    task_id: str
    source_revision: str
    model_slug: str
    reasoning_effort: str
    family: str
    condition_contract: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _SubmissionAuditSources:
    revision: bool | None
    initial_submission: SubmissionState
    final_submission: SubmissionState
    initial_verifier: VerifierScores | None
    final_verifier: VerifierScores | None


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _digest_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise TrajectoryTelemetryError(f"expected regular file: {path}")
    return _digest_bytes(path.read_bytes())


def _load_object(path: Path, *, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise TrajectoryTelemetryError(f"missing {label}")
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrajectoryTelemetryError(f"malformed {label}") from exc
    if not isinstance(value, dict):
        raise TrajectoryTelemetryError(f"{label} must be a JSON object")
    return value


def _required(mapping: Mapping[str, Any], key: str, expected: type, label: str) -> Any:
    value = mapping.get(key)
    if not isinstance(value, expected):
        raise TrajectoryTelemetryError(
            f"{label}.{key} has the wrong type or is missing"
        )
    return value


def verify_artifact_index(root: Path) -> str:
    """Verify every indexed byte and reject omitted, duplicate, or escaped files."""

    if root.is_symlink() or not root.is_dir():
        raise TrajectoryTelemetryError("run root must be a regular directory")
    index_path = root / "artifact-index.json"
    try:
        index = _ArtifactIndex.model_validate(
            _load_object(index_path, label="artifact-index.json")
        )
    except ValidationError as exc:
        raise TrajectoryTelemetryError("artifact index violates schema v1") from exc
    names = [entry.path for entry in index.files]
    if names != sorted(names) or len(names) != len(set(names)):
        raise TrajectoryTelemetryError("artifact index paths must be sorted and unique")
    for entry in index.files:
        relative = PurePosixPath(entry.path)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise TrajectoryTelemetryError("artifact index contains an unsafe path")
        path = root.joinpath(*relative.parts)
        try:
            path.resolve(strict=True).relative_to(root.resolve(strict=True))
        except (OSError, ValueError) as exc:
            raise TrajectoryTelemetryError(
                "artifact index path escapes the run"
            ) from exc
        if path.stat().st_size != entry.bytes or _digest_file(path) != entry.digest:
            raise TrajectoryTelemetryError(f"artifact mismatch: {entry.path}")
    actual = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != index_path
    )
    if any(path.is_symlink() for path in root.rglob("*")):
        raise TrajectoryTelemetryError("run artifacts contain a symlink")
    if actual != names:
        raise TrajectoryTelemetryError("artifact index does not exactly cover the run")
    return _digest_file(index_path)


def _verify_snapshot(root: Path) -> dict[str, Any]:
    snapshot = _load_object(root / "runtime-snapshot.json", label="runtime snapshot")
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise TrajectoryTelemetryError("runtime snapshot schema version is unsupported")
    snapshot_id = _required(snapshot, "snapshot_id", str, "runtime_snapshot")
    body = {key: value for key, value in snapshot.items() if key != "snapshot_id"}
    if _digest_bytes(_canonical_bytes(body)) != snapshot_id:
        raise TrajectoryTelemetryError("runtime snapshot ID is inconsistent")
    prompts = _required(snapshot, "prompts", dict, "runtime_snapshot")
    for stage in ("primary", "audit"):
        expected = _required(
            prompts, f"{stage}_digest", str, "runtime_snapshot.prompts"
        )
        if _digest_file(root / f"{stage}-prompt.txt") != expected:
            raise TrajectoryTelemetryError(f"{stage} prompt digest is inconsistent")
    return snapshot


def _strict_jsonl(path: Path, *, label: str) -> list[dict[str, Any]]:
    if path.is_symlink() or not path.is_file():
        raise TrajectoryTelemetryError(f"missing {label}")
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_bytes().splitlines(), start=1):
        try:
            event = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TrajectoryTelemetryError(
                f"malformed {label} line {line_number}"
            ) from exc
        if not isinstance(event, dict):
            raise TrajectoryTelemetryError(
                f"{label} line {line_number} is not an object"
            )
        events.append(event)
    return events


def _text_payload(item: Mapping[str, Any]) -> dict[str, Any] | None:
    result = item.get("result")
    if not isinstance(result, Mapping):
        return None
    for key in ("structured_content", "structuredContent"):
        value = result.get(key)
        if isinstance(value, dict):
            return value
    content = result.get("content")
    if not isinstance(content, list):
        return None
    for block in content:
        if not isinstance(block, Mapping) or not isinstance(block.get("text"), str):
            continue
        try:
            value = json.loads(block["text"])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _collect_codes(value: object) -> set[str | int]:
    codes: set[str | int] = set()
    if isinstance(value, Mapping):
        code = value.get("code")
        if isinstance(code, str | int) and not isinstance(code, bool):
            codes.add(code)
        for item in value.values():
            codes.update(_collect_codes(item))
    elif isinstance(value, list):
        for item in value:
            codes.update(_collect_codes(item))
    return codes


def _contains_uri(value: object, uri: str) -> int:
    if value == uri:
        return 1
    if isinstance(value, Mapping):
        return sum(_contains_uri(item, uri) for item in value.values())
    if isinstance(value, list):
        return sum(_contains_uri(item, uri) for item in value)
    return 0


def _nested_string(value: object, *path: str) -> str | None:
    current = value
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current if isinstance(current, str) else None


def _invoke_items(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for event in events:
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, Mapping)
            and item.get("type") == "mcp_tool_call"
            and item.get("tool") == "capability.invoke"
        ):
            calls.append(dict(item))
    return calls


def _call_argument_digest(arguments: object) -> str:
    try:
        return _digest_bytes(_canonical_bytes(arguments))
    except (TypeError, ValueError):
        return _digest_bytes(b"unserializable\n")


def _call_failed(item: Mapping[str, Any], response: Mapping[str, Any] | None) -> bool:
    result = item.get("result")
    execution = response.get("execution") if isinstance(response, Mapping) else None
    execution_status = (
        execution.get("status") if isinstance(execution, Mapping) else None
    )
    return bool(
        item.get("status") in {"error", "failed"}
        or item.get("error")
        or (isinstance(result, Mapping) and result.get("isError") is True)
        or execution_status in {"ERROR", "TIMEOUT", "CANCELLED"}
    )


def _produced_rule(
    capability_id: str | None,
    response: Mapping[str, Any] | None,
) -> tuple[str | None, tuple[str, ...], bool]:
    if capability_id is None or not isinstance(response, Mapping):
        return None, (), False
    rule = PRODUCER_RULES.get(capability_id)
    if rule is None:
        return None, (), False
    kind, checkers = rule
    output = response.get("output")
    produced = isinstance(output, Mapping) and output.get(kind) is not None
    return kind, checkers, produced


def _task_relevant(capability_id: str | None, family: str) -> bool | None:
    if capability_id is None:
        return None
    allowed = TASK_FAMILY_DOMAINS.get(family)
    if allowed is None:
        raise TrajectoryTelemetryError(f"unknown symbolic task family: {family}")
    return capability_id.split(".", 1)[0] in allowed


def _capability_calls(
    events: Sequence[Mapping[str, Any]], family: str
) -> tuple[list[CapabilityCall], int]:
    items = _invoke_items(events)
    seen_signatures: Counter[tuple[object, str]] = Counter()
    records: list[CapabilityCall] = []
    recovered = 0
    for sequence, item in enumerate(items):
        arguments = item.get("arguments")
        response = _text_payload(item)
        capability_id = (
            arguments.get("capability_id")
            if isinstance(arguments, Mapping)
            and isinstance(arguments.get("capability_id"), str)
            else None
        )
        codes = _collect_codes(item)
        codes.update(_collect_codes(response))
        schema_valid = (
            isinstance(arguments, Mapping)
            and capability_id is not None
            and isinstance(arguments.get("payload"), Mapping)
            and not bool(codes & PARAMETER_ERROR_CODES)
        )
        execution_status = _nested_string(response, "execution", "status")
        executable = schema_valid and execution_status is not None
        failed = _call_failed(item, response)
        output_status = _nested_string(response, "output", "status") or _nested_string(
            response, "output", "stop_reason"
        )
        completeness = _nested_string(response, "completeness", "status")
        produced_kind, checkers, has_produced_output = _produced_rule(
            capability_id, response
        )
        produced = (
            has_produced_output and execution_status == "COMPLETED" and not failed
        )
        artifacts_raw = (
            response.get("artifact_uris") if isinstance(response, Mapping) else None
        )
        artifacts = (
            sorted(item for item in artifacts_raw if isinstance(item, str))
            if isinstance(artifacts_raw, list)
            else []
        )
        checker_followed: bool | None = None
        if produced:
            checker_followed = any(
                isinstance(later.get("arguments"), Mapping)
                and later["arguments"].get("capability_id") in checkers
                and _nested_string(_text_payload(later), "execution", "status")
                == "COMPLETED"
                and not _call_failed(later, _text_payload(later))
                for later in items[sequence + 1 :]
            )
        later_success = any(
            isinstance(later.get("arguments"), Mapping)
            and later["arguments"].get("capability_id") == capability_id
            and _nested_string(_text_payload(later), "execution", "status")
            == "COMPLETED"
            and not _call_failed(later, _text_payload(later))
            for later in items[sequence + 1 :]
        )
        if failed and later_success:
            recovered += 1
        digest = _call_argument_digest(arguments)
        signature = (item.get("tool"), digest)
        repeated = seen_signatures[signature] > 0
        seen_signatures[signature] += 1
        records.append(
            CapabilityCall(
                sequence=sequence,
                capability_id=capability_id,
                argument_digest=digest,
                schema_valid=schema_valid,
                executable=executable,
                failed=failed,
                repeated=repeated,
                task_relevant=_task_relevant(capability_id, family),
                execution_status=execution_status,
                output_status=output_status,
                completeness_status=completeness,
                produced_kind=produced_kind,
                produced=produced,
                applicable_checker_ids=list(checkers),
                checker_followed=checker_followed,
                artifact_uris=artifacts,
                error_codes=sorted(str(code) for code in codes),
            )
        )
    return records, recovered


def _token_usage(value: object) -> TokenUsage:
    if not isinstance(value, Mapping):
        return TokenUsage(availability="UNAVAILABLE")
    required = ("input_tokens", "output_tokens")
    if not all(
        isinstance(value.get(key), int) and not isinstance(value.get(key), bool)
        for key in required
    ):
        return TokenUsage(availability="UNAVAILABLE")
    input_tokens = int(value["input_tokens"])
    output_tokens = int(value["output_tokens"])
    explicit_total = value.get("total_tokens")
    total = (
        int(explicit_total)
        if isinstance(explicit_total, int) and not isinstance(explicit_total, bool)
        else input_tokens + output_tokens
    )
    optional = {
        key: int(value[key])
        if isinstance(value.get(key), int) and not isinstance(value.get(key), bool)
        else None
        for key in (
            "cached_input_tokens",
            "cache_write_input_tokens",
            "reasoning_output_tokens",
        )
    }
    return TokenUsage(
        availability="EXACT",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total,
        **optional,
    )


def _timing(path: Path, *, required: bool) -> float | None:
    if not path.exists() and not required:
        return None
    value = _load_object(path, label=path.name)
    elapsed = value.get("elapsed_seconds")
    if not isinstance(elapsed, int | float) or isinstance(elapsed, bool) or elapsed < 0:
        raise TrajectoryTelemetryError(f"{path.name} omitted exact elapsed_seconds")
    return float(elapsed)


def _submission(path: Path, schema: Mapping[str, Any]) -> SubmissionState:
    if not path.exists():
        return SubmissionState(
            present=False,
            schema_valid=None,
            digest=None,
            conclusion=None,
            verdict=None,
            claimed_assurance=None,
            scope=None,
            completeness=None,
        )
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return SubmissionState(
            present=True,
            schema_valid=False,
            digest=_digest_file(path),
            conclusion=None,
            verdict=None,
            claimed_assurance=None,
            scope=None,
            completeness=None,
        )
    valid = not list(Draft202012Validator(schema).iter_errors(value))
    mapping = value if isinstance(value, Mapping) else {}
    raw_result = mapping.get("result")
    result: Mapping[str, Any] = raw_result if isinstance(raw_result, Mapping) else {}
    return SubmissionState(
        present=True,
        schema_valid=valid,
        digest=_digest_file(path),
        conclusion=mapping.get("conclusion")
        if isinstance(mapping.get("conclusion"), str)
        else None,
        verdict=result.get("verdict")
        if isinstance(result.get("verdict"), str)
        else None,
        claimed_assurance=mapping.get("claimed_assurance")
        if isinstance(mapping.get("claimed_assurance"), str)
        else None,
        scope=mapping.get("scope") if isinstance(mapping.get("scope"), str) else None,
        completeness=mapping.get("completeness")
        if isinstance(mapping.get("completeness"), str)
        else None,
    )


def _submission_tree_digest(root: Path) -> str | None:
    if not root.exists():
        return None
    if root.is_symlink() or not root.is_dir():
        raise TrajectoryTelemetryError("submission snapshot must be a directory")
    files: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise TrajectoryTelemetryError(
                "submission snapshot contains an unsafe file"
            )
        if path.is_file():
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "digest": _digest_file(path),
                }
            )
    return _digest_bytes(_canonical_bytes(files))


def _verifier(value: object) -> VerifierScores | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TrajectoryTelemetryError("verifier result must be an object or null")
    if value.get("verifier_workspace_outside_model_workspace") is not True:
        raise TrajectoryTelemetryError("verifier result lacks clean-room provenance")
    reward = _required(value, "reward", dict, "verifier")
    try:
        return VerifierScores(
            execution_status=_required(value, "execution_status", str, "verifier"),
            mathematical_observation=_required(
                value, "mathematical_observation", str, "verifier"
            ),
            correctness=reward["correctness"],
            evidence_validity=reward["evidence_validity"],
            scope_accuracy=reward["scope_accuracy"],
            assurance_calibration=reward["assurance_calibration"],
            input_binding=reward["input_binding"],
            artifact_binding=reward["artifact_binding"],
            protocol_compliance=reward["protocol_compliance"],
            false_certification=reward["false_certification"],
            reward=reward["reward"],
        )
    except (KeyError, ValidationError) as exc:
        raise TrajectoryTelemetryError(
            "verifier result violates its score contract"
        ) from exc


def _audit_classification(
    condition: str,
    revision: bool | None,
    initial: VerifierScores | None,
    final: VerifierScores | None,
) -> AuditClassification:
    if condition not in {"C", "D"}:
        return "NOT_APPLICABLE"
    if initial is None or final is None:
        return "INCOMPLETE"
    initial_ok = initial.reward == 1.0
    final_ok = final.reward == 1.0
    if initial_ok and final_ok:
        return "ALREADY_CORRECT"
    if not initial_ok and final_ok and revision is True:
        return "REPAIR"
    if initial_ok and not final_ok and revision is True:
        return "REGRESSION"
    return "UNCHANGED_FAILURE"


def _reasoning(
    root: Path,
    condition: str,
    condition_snapshot: Mapping[str, Any],
    telemetry: Mapping[str, Any],
) -> ReasoningProtocol:
    mode = _required(condition_snapshot, "reasoning_log_mode", str, "condition")
    protocol = _required(telemetry, "reasoning_protocol", dict, "primary.telemetry")
    counts = {
        phase.lower(): protocol.get(f"{phase.lower()}_count")
        for phase in REASONING_PHASES
    }
    if not all(
        isinstance(value, int) and not isinstance(value, bool) and value >= 0
        for value in counts.values()
    ):
        raise TrajectoryTelemetryError("reasoning protocol counts are malformed")
    if mode == "OFF":
        return ReasoningProtocol(
            mode="OFF",
            compliance="NOT_APPLICABLE",
            plan_count=counts["plan"],
            before_tool_count=counts["before_tool"],
            after_tool_count=counts["after_tool"],
            final_count=counts["final"],
            log_status="NOT_APPLICABLE",
            log_entries=0,
            log_bytes=0,
            token_overhead_availability="UNAVAILABLE",
            token_overhead_tokens=None,
        )
    if mode != "REQUIRED":
        raise TrajectoryTelemetryError(f"unsupported reasoning-log mode: {mode}")
    index = _load_object(
        root / condition / "reasoning-logs" / "index.json", label="reasoning-log index"
    )
    status = _required(index, "status", str, "reasoning_logs")
    runs = _required(index, "runs", list, "reasoning_logs")
    if status not in {"EMPTY", "EXPORTED"}:
        raise TrajectoryTelemetryError("reasoning-log status is invalid")
    entries = 0
    byte_count = 0
    for run in runs:
        if not isinstance(run, Mapping):
            raise TrajectoryTelemetryError("reasoning-log run entry is malformed")
        relative = _required(run, "path", str, "reasoning_log_run")
        if PurePosixPath(relative).name != relative:
            raise TrajectoryTelemetryError("reasoning-log path is unsafe")
        log = root / condition / "reasoning-logs" / relative
        log_events = _strict_jsonl(log, label="reasoning log")
        declared_count = _required(run, "event_count", int, "reasoning_log_run")
        if len(log_events) != declared_count or _digest_file(log) != run.get("digest"):
            raise TrajectoryTelemetryError(
                "reasoning-log count or digest is inconsistent"
            )
        entries += declared_count
        byte_count += log.stat().st_size
    successful_reasoning_writes = (
        sum(
            1
            for name in telemetry.get("successful_tool_calls", [])
            if name == "reasoning.write"
        )
        if isinstance(telemetry.get("successful_tool_calls"), list)
        else 0
    )
    if successful_reasoning_writes != entries:
        raise TrajectoryTelemetryError(
            "reasoning-log export disagrees with successful writes"
        )
    return ReasoningProtocol(
        mode="REQUIRED",
        compliance="COMPLETE" if protocol.get("status") == "COMPLETE" else "INCOMPLETE",
        plan_count=counts["plan"],
        before_tool_count=counts["before_tool"],
        after_tool_count=counts["after_tool"],
        final_count=counts["final"],
        log_status=status,
        log_entries=entries,
        log_bytes=byte_count,
        token_overhead_availability="UNAVAILABLE",
        token_overhead_tokens=None,
    )


def _search_outcomes(
    calls: Sequence[CapabilityCall], final: SubmissionState
) -> SearchOutcomeMetrics:
    timeout = sum(
        call.execution_status == "TIMEOUT" or call.output_status == "TIMEOUT"
        for call in calls
    )
    cancelled = sum(
        call.execution_status == "CANCELLED" or call.output_status == "CANCELLED"
        for call in calls
    )
    incomplete = sum(
        call.execution_status == "INCOMPLETE"
        or call.output_status in {"INCOMPLETE", "UNKNOWN"}
        or call.completeness_status in {"INCOMPLETE", "UNKNOWN"}
        for call in calls
    )
    bounded = sum(call.output_status == "GRID_EXHAUSTED" for call in calls)
    unresolved = 0
    for index, call in enumerate(calls):
        nonconclusive = (
            call.execution_status in NONCONCLUSIVE_STATUSES
            or call.output_status in NONCONCLUSIVE_STATUSES
            or call.completeness_status in {"INCOMPLETE", "UNKNOWN"}
        )
        recovered = any(
            later.capability_id == call.capability_id
            and later.execution_status == "COMPLETED"
            and not later.failed
            for later in calls[index + 1 :]
        )
        unresolved += bool(nonconclusive and not recovered)
    overclaim = bool(
        unresolved and final.present and final.conclusion not in {None, "UNKNOWN"}
    )
    return SearchOutcomeMetrics(
        timeout_count=timeout,
        cancellation_count=cancelled,
        incomplete_count=incomplete,
        bounded_exhaustion_count=bounded,
        unresolved_nonconclusive_count=unresolved,
        final_claim_improperly_escalates=overclaim,
    )


def _artifact_flow(
    calls: Sequence[CapabilityCall],
    raw_items: Sequence[Mapping[str, Any]],
    final_verifier: VerifierScores | None,
) -> ArtifactFlow:
    created = sorted({uri for call in calls for uri in call.artifact_uris})
    handoffs = 0
    reused: set[str] = set()
    for index, item in enumerate(raw_items):
        response = _text_payload(item)
        artifacts = (
            response.get("artifact_uris") if isinstance(response, Mapping) else None
        )
        if not isinstance(artifacts, list):
            continue
        for uri in (uri for uri in artifacts if isinstance(uri, str)):
            count = sum(
                _contains_uri(later.get("arguments"), uri)
                for later in raw_items[index + 1 :]
            )
            handoffs += count
            if count:
                reused.add(uri)
    return ArtifactFlow(
        created_uris=created,
        handoff_count=handoffs,
        reused_uri_count=len(reused),
        stale_binding_failure_count=sum(
            code in STALE_BINDING_CODES for call in calls for code in call.error_codes
        ),
        substitution_failure_count=sum(
            code in SUBSTITUTION_CODES for call in calls for code in call.error_codes
        ),
        final_input_binding_valid=(final_verifier.input_binding == 1.0)
        if final_verifier
        else None,
        final_artifact_binding_valid=(final_verifier.artifact_binding == 1.0)
        if final_verifier
        else None,
    )


def _protocol_violations(
    calls: Sequence[CapabilityCall],
    outcomes: SearchOutcomeMetrics,
    artifact_flow: ArtifactFlow,
    reasoning: ReasoningProtocol,
    infrastructure_status: str,
) -> list[str]:
    violations: set[str] = set()
    if any(not call.schema_valid for call in calls):
        violations.add("INVALID_CAPABILITY_CALL")
    if any(call.produced and call.checker_followed is False for call in calls):
        violations.add("MISSING_APPLICABLE_CHECKER")
    if any(call.task_relevant is False for call in calls):
        violations.add("TASK_IRRELEVANT_CALL")
    if outcomes.final_claim_improperly_escalates:
        violations.add("UNRESOLVED_NONCONCLUSIVE_OVERCLAIM")
    if artifact_flow.stale_binding_failure_count:
        violations.add("STALE_ARTIFACT_BINDING")
    if artifact_flow.substitution_failure_count:
        violations.add("ARTIFACT_SUBSTITUTION")
    if reasoning.compliance == "INCOMPLETE":
        violations.add("REASONING_PROTOCOL_INCOMPLETE")
    if infrastructure_status == "INCOMPLETE":
        violations.add("INCOMPLETE_INFRASTRUCTURE")
    return sorted(violations)


def _validate_telemetry_replay(
    path: Path, source: Mapping[str, Any], parsed: Mapping[str, Any]
) -> None:
    for key, value in parsed.items():
        if source.get(key) != value:
            raise TrajectoryTelemetryError(
                f"{path.name} disagrees with raw Codex JSONL at {key}"
            )


def _condition_identity(
    root: Path,
    snapshot: Mapping[str, Any],
    condition: Condition,
    result: Mapping[str, Any],
) -> _ConditionIdentity:
    condition_root = root / condition
    if result.get("schema_version") != SCHEMA_VERSION:
        raise TrajectoryTelemetryError(
            f"{condition} condition result schema version is unsupported"
        )
    snapshot_id = _required(snapshot, "snapshot_id", str, "runtime_snapshot")
    if result.get("snapshot_id") != snapshot_id or result.get("condition") != condition:
        raise TrajectoryTelemetryError(f"{condition} condition binding is inconsistent")
    task = _required(snapshot, "task", dict, "runtime_snapshot")
    task_id = _required(task, "id", str, "runtime_snapshot.task")
    source = _required(snapshot, "source", dict, "runtime_snapshot")
    source_revision = _required(source, "revision", str, "runtime_snapshot.source")
    model = _required(snapshot, "model", dict, "runtime_snapshot")
    model_slug = _required(model, "slug", str, "runtime_snapshot.model")
    reasoning_effort = _required(snapshot, "reasoning_effort", str, "runtime_snapshot")
    if (
        result.get("model") != model_slug
        or result.get("reasoning_effort") != reasoning_effort
    ):
        raise TrajectoryTelemetryError(f"{condition} model contract drifted")
    workspace_input = _load_object(
        condition_root / "workspace" / "input.json", label=f"{condition} input"
    )
    family = _required(workspace_input, "family", str, f"{condition}.input")
    if workspace_input.get("case_id") != task_id:
        raise TrajectoryTelemetryError(f"{condition} task input is misbound")
    public_hashes = _required(task, "public_file_hashes", dict, "runtime_snapshot.task")
    for name in ("input.json", "instruction.md", "submission_schema.json"):
        if _digest_file(condition_root / "workspace" / name) != public_hashes.get(name):
            raise TrajectoryTelemetryError(
                f"{condition} public task file drifted: {name}"
            )
    condition_contracts = _required(snapshot, "conditions", dict, "runtime_snapshot")
    condition_contract = _required(
        condition_contracts, condition, dict, "runtime_snapshot.conditions"
    )
    return _ConditionIdentity(
        snapshot_id=snapshot_id,
        task_id=task_id,
        source_revision=source_revision,
        model_slug=model_slug,
        reasoning_effort=reasoning_effort,
        family=family,
        condition_contract=condition_contract,
    )


def _stage_sources(
    path: Path, telemetry_path: Path, *, label: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events = _strict_jsonl(path, label=label)
    parsed = parse_agent_transcript(path)
    source = _load_object(telemetry_path, label=f"{label} telemetry")
    _validate_telemetry_replay(path, source, parsed)
    return events, source


def _stage_summary(
    source: Mapping[str, Any] | None, *, include_capability_ids: bool
) -> tuple[object, dict[str, object] | None]:
    if source is None:
        return None, None
    mcp_calls = source.get("mcp_calls")
    shell_calls = source.get("shell_calls")
    if not isinstance(mcp_calls, list) or not isinstance(shell_calls, list):
        raise TrajectoryTelemetryError("stage tool-call telemetry is malformed")
    calls: dict[str, object] = {"mcp": mcp_calls, "shell": shell_calls}
    if include_capability_ids:
        capability_ids = source.get("capability_ids")
        if not isinstance(capability_ids, list):
            raise TrajectoryTelemetryError("stage capability telemetry is malformed")
        calls["capability_ids"] = capability_ids
    return source.get("usage"), calls


def _validate_stage_summary(
    result: Mapping[str, Any],
    label: Literal["primary", "audit"],
    source: Mapping[str, Any] | None,
) -> None:
    expected_usage, expected_calls = _stage_summary(
        source, include_capability_ids=label == "primary"
    )
    if result.get(f"{label}_usage") != expected_usage:
        raise TrajectoryTelemetryError(
            f"condition result {label} usage disagrees with raw telemetry"
        )
    if result.get(f"{label}_tool_calls") != expected_calls:
        raise TrajectoryTelemetryError(
            f"condition result {label} tool calls disagree with raw telemetry"
        )


def _validate_reasoning_summary(
    condition_root: Path,
    condition: Condition,
    result: Mapping[str, Any],
) -> None:
    expected: object = None
    if condition in {"B", "C", "D"}:
        expected = _load_object(
            condition_root / "reasoning-logs" / "index.json",
            label="reasoning-log index",
        )
    if result.get("reasoning_logs") != expected:
        raise TrajectoryTelemetryError(
            f"{condition} reasoning-log summary disagrees with raw artifacts"
        )


def _submission_audit_sources(
    condition_root: Path,
    condition: Condition,
    result: Mapping[str, Any],
) -> _SubmissionAuditSources:
    schema = _load_object(
        condition_root / "workspace" / "submission_schema.json",
        label=f"{condition} submission schema",
    )
    initial_submission = _submission(
        condition_root / "pre-audit" / "submission.json", schema
    )
    final_submission = _submission(condition_root / "final" / "submission.json", schema)
    revision = result.get("revision_applied")
    if revision is not None and not isinstance(revision, bool):
        raise TrajectoryTelemetryError(f"{condition} revision flag is malformed")
    if condition not in {"C", "D"} and revision is not None:
        raise TrajectoryTelemetryError(f"{condition} cannot declare an audit revision")
    if (
        initial_submission.present
        and final_submission.present
        and condition
        in {
            "C",
            "D",
        }
    ):
        actual_revision = _submission_tree_digest(
            condition_root / "pre-audit"
        ) != _submission_tree_digest(condition_root / "final")
        if revision is not actual_revision:
            raise TrajectoryTelemetryError(
                "audit revision flag disagrees with artifacts"
            )
    initial_raw = result.get("initial_verifier")
    final_raw = result.get("verifier")
    if condition not in {"C", "D"} and initial_raw != final_raw:
        raise TrajectoryTelemetryError(
            f"{condition} initial and final verifier results disagree"
        )
    for name, expected in (
        ("initial-verifier-result.json", initial_raw),
        ("verifier-result.json", final_raw),
    ):
        path = condition_root / name
        if path.exists() and _load_object(path, label=name) != expected:
            raise TrajectoryTelemetryError(f"{condition} {name} is inconsistent")
        if expected is not None and not path.exists():
            raise TrajectoryTelemetryError(f"{condition} {name} is missing")
    return _SubmissionAuditSources(
        revision=revision,
        initial_submission=initial_submission,
        final_submission=final_submission,
        initial_verifier=_verifier(initial_raw),
        final_verifier=_verifier(final_raw),
    )


def _infrastructure(
    result: Mapping[str, Any], condition: Condition
) -> tuple[InfrastructureStatus, list[str]]:
    status = _required(result, "infrastructure_status", str, f"{condition}.result")
    failures = _required(result, "infrastructure_failures", list, f"{condition}.result")
    if status not in {"COMPLETE", "INCOMPLETE"}:
        raise TrajectoryTelemetryError(f"{condition} infrastructure status is invalid")
    if status == "COMPLETE" and failures:
        raise TrajectoryTelemetryError(
            f"{condition} complete infrastructure has failures"
        )
    if status == "INCOMPLETE" and not failures:
        raise TrajectoryTelemetryError(
            f"{condition} incomplete infrastructure lacks failures"
        )
    return cast(InfrastructureStatus, status), [str(item) for item in failures]


def _audit_usage_and_time(
    condition_root: Path, condition: Condition
) -> tuple[dict[str, Any] | None, TokenUsage | None, float | None]:
    audit_path = condition_root / "audit.codex.jsonl"
    if condition not in {"C", "D"}:
        if audit_path.exists():
            raise TrajectoryTelemetryError(
                f"{condition} unexpectedly contains an audit stage"
            )
        return None, None, None
    if not audit_path.exists():
        return None, None, None
    _, source = _stage_sources(
        audit_path,
        condition_root / "audit.telemetry.json",
        label=f"{condition} second-stage JSONL",
    )
    return (
        source,
        _token_usage(source.get("usage")),
        _timing(condition_root / "audit.timing.json", required=True),
    )


def _validate_complete_sources(
    condition: Condition,
    primary_usage: TokenUsage,
    audit_usage: TokenUsage | None,
    submissions: _SubmissionAuditSources,
    infrastructure_status: InfrastructureStatus,
) -> None:
    if infrastructure_status != "COMPLETE":
        return
    if primary_usage.availability != "EXACT":
        raise TrajectoryTelemetryError(
            f"{condition} complete infrastructure has unavailable primary token usage"
        )
    if (
        not submissions.initial_submission.present
        or not submissions.final_submission.present
    ):
        raise TrajectoryTelemetryError(
            f"{condition} complete infrastructure lacks a preserved submission"
        )
    if submissions.initial_verifier is None or submissions.final_verifier is None:
        raise TrajectoryTelemetryError(
            f"{condition} complete infrastructure lacks clean-room verifier results"
        )
    if condition in {"C", "D"}:
        if audit_usage is None or audit_usage.availability != "EXACT":
            raise TrajectoryTelemetryError(
                "C complete infrastructure has unavailable audit token usage"
                if condition == "C"
                else "D complete infrastructure has unavailable feedback-stage token usage"
            )
        if submissions.revision is None:
            raise TrajectoryTelemetryError(
                f"{condition} complete infrastructure lacks a revision decision"
            )


def _call_metrics(
    source: Mapping[str, Any], calls: Sequence[CapabilityCall], recovered: int
) -> CallMetrics:
    all_mcp = source.get("mcp_calls")
    all_shell = source.get("shell_calls")
    if not isinstance(all_mcp, list) or not isinstance(all_shell, list):
        raise TrajectoryTelemetryError("tool-call telemetry is malformed")
    return CallMetrics(
        mcp_calls=len(all_mcp),
        shell_calls=len(all_shell),
        discovery_calls=sum(name == "capability.describe" for name in all_mcp),
        invocation_calls=len(calls),
        schema_valid_calls=sum(call.schema_valid for call in calls),
        executable_calls=sum(call.executable for call in calls),
        failed_calls=sum(call.failed for call in calls),
        repeated_calls=sum(call.repeated for call in calls),
        task_irrelevant_calls=sum(call.task_relevant is False for call in calls),
        producer_calls=sum(call.capability_id in PRODUCER_IDS for call in calls),
        checker_calls=sum(call.capability_id in CHECKER_IDS for call in calls),
        candidate_or_witness_productions=sum(call.produced for call in calls),
        missing_applicable_checker=sum(
            call.produced and call.checker_followed is False for call in calls
        ),
        recovered_calls=recovered,
    )


def _condition_record(
    root: Path,
    artifact_index_digest: str,
    snapshot: Mapping[str, Any],
    condition: Condition,
) -> RunTelemetry:
    condition_root = root / condition
    result = _load_object(
        condition_root / "condition-result.json", label=f"{condition} condition result"
    )
    identity = _condition_identity(root, snapshot, condition, result)
    events, primary_source = _stage_sources(
        condition_root / "primary.codex.jsonl",
        condition_root / "primary.telemetry.json",
        label=f"{condition} primary JSONL",
    )
    _validate_stage_summary(result, "primary", primary_source)
    calls, recovered_calls = _capability_calls(events, identity.family)
    raw_items = _invoke_items(events)
    reasoning = _reasoning(root, condition, identity.condition_contract, primary_source)
    _validate_reasoning_summary(condition_root, condition, result)
    submissions = _submission_audit_sources(condition_root, condition, result)
    infrastructure_status, failures = _infrastructure(result, condition)
    primary_usage = _token_usage(primary_source.get("usage"))
    audit_source, audit_usage, audit_seconds = _audit_usage_and_time(
        condition_root, condition
    )
    _validate_stage_summary(result, "audit", audit_source)
    _validate_complete_sources(
        condition,
        primary_usage,
        audit_usage,
        submissions,
        infrastructure_status,
    )
    primary_seconds = _timing(condition_root / "primary.timing.json", required=True)
    total_seconds = (
        None if primary_seconds is None else primary_seconds + (audit_seconds or 0.0)
    )
    outcomes = _search_outcomes(calls, submissions.final_submission)
    artifact_flow = _artifact_flow(calls, raw_items, submissions.final_verifier)
    audit_class = _audit_classification(
        condition,
        submissions.revision,
        submissions.initial_verifier,
        submissions.final_verifier,
    )
    violations = _protocol_violations(
        calls, outcomes, artifact_flow, reasoning, infrastructure_status
    )
    return RunTelemetry(
        telemetry_schema_version="1",
        source_artifact_index_digest=artifact_index_digest,
        snapshot_id=identity.snapshot_id,
        source_revision=identity.source_revision,
        task_id=identity.task_id,
        task_family=identity.family,
        condition=condition,
        model=identity.model_slug,
        reasoning_effort=identity.reasoning_effort,
        infrastructure_status=infrastructure_status,
        infrastructure_failures=failures,
        usage=StageUsage(primary=primary_usage, audit=audit_usage),
        wall_time=WallTime(
            primary_seconds=primary_seconds,
            audit_seconds=audit_seconds,
            total_seconds=total_seconds,
        ),
        calls=_call_metrics(primary_source, calls, recovered_calls),
        capability_calls=calls,
        search_outcomes=outcomes,
        artifact_flow=artifact_flow,
        reasoning_protocol=reasoning,
        audit=AuditComparison(
            revision_applied=submissions.revision,
            classification=audit_class,
            initial_submission=submissions.initial_submission,
            final_submission=submissions.final_submission,
            initial_verifier=submissions.initial_verifier,
            final_verifier=submissions.final_verifier,
        ),
        classification=TrajectoryClassification(
            protocol_violations=violations,
            successful_recovery=bool(recovered_calls or audit_class == "REPAIR"),
            audit_outcome=audit_class,
        ),
    )


def analyze_run(root: Path) -> list[RunTelemetry]:
    """Verify and normalize one A/B/C run or one PR5 condition-D run root."""

    index_digest = verify_artifact_index(root)
    snapshot = _verify_snapshot(root)
    run_result = _load_object(root / "run-result.json", label="run result")
    if run_result.get("schema_version") != SCHEMA_VERSION:
        raise TrajectoryTelemetryError("run result schema version is unsupported")
    if run_result.get("snapshot_id") != snapshot.get("snapshot_id"):
        raise TrajectoryTelemetryError("run result is not bound to the snapshot")
    task = _required(snapshot, "task", dict, "runtime_snapshot")
    if run_result.get("task") != task.get("id"):
        raise TrajectoryTelemetryError("run result is not bound to the snapshot task")
    raw_conditions = _required(run_result, "conditions", list, "run_result")
    condition_names = [
        item.get("condition") for item in raw_conditions if isinstance(item, Mapping)
    ]
    if len(condition_names) != len(raw_conditions) or len(condition_names) != len(
        set(condition_names)
    ):
        raise TrajectoryTelemetryError("run conditions are malformed or duplicated")
    if any(name not in CONDITIONS for name in condition_names):
        raise TrajectoryTelemetryError("run contains an unknown condition")
    conditions = cast(list[Condition], condition_names)
    records = [
        _condition_record(root, index_digest, snapshot, condition)
        for condition in conditions
    ]
    for source_record, record in zip(raw_conditions, records, strict=True):
        persisted = _load_object(
            root / record.condition / "condition-result.json", label="condition result"
        )
        if source_record != persisted:
            raise TrajectoryTelemetryError(
                "run-result condition disagrees with persisted condition"
            )
    expected_status = (
        "COMPLETE"
        if all(record.infrastructure_status == "COMPLETE" for record in records)
        else "INCOMPLETE"
    )
    if run_result.get("status") != expected_status:
        raise TrajectoryTelemetryError(
            "run status disagrees with condition infrastructure"
        )
    return records


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _exact_run_tokens(record: RunTelemetry) -> int | None:
    primary = record.usage.primary
    if primary.availability != "EXACT" or primary.total_tokens is None:
        return None
    if record.condition not in {"C", "D"}:
        return primary.total_tokens
    audit = record.usage.audit
    if audit is None or audit.availability != "EXACT" or audit.total_tokens is None:
        return None
    return primary.total_tokens + audit.total_tokens


def _aggregate_row(
    task_id: str, condition: AggregateCondition, records: Sequence[RunTelemetry]
) -> AggregateRow:
    verifiers = [
        record.audit.final_verifier
        for record in records
        if record.audit.final_verifier is not None
    ]
    exact_tokens = [
        tokens
        for record in records
        if (tokens := _exact_run_tokens(record)) is not None
    ]
    exact_wall = [
        seconds
        for record in records
        if (seconds := record.wall_time.total_seconds) is not None
    ]
    reasoning_overhead = [
        tokens
        for record in records
        if record.reasoning_protocol.token_overhead_availability == "EXACT"
        and (tokens := record.reasoning_protocol.token_overhead_tokens) is not None
    ]
    audit_counts = Counter(record.audit.classification for record in records)
    return AggregateRow(
        task_id=task_id,
        condition=condition,
        run_count=len(records),
        infrastructure_complete=sum(
            record.infrastructure_status == "COMPLETE" for record in records
        ),
        correctness_mean=_mean([item.correctness for item in verifiers]),
        evidence_validity_mean=_mean([item.evidence_validity for item in verifiers]),
        scope_accuracy_mean=_mean([item.scope_accuracy for item in verifiers]),
        assurance_calibration_mean=_mean(
            [item.assurance_calibration for item in verifiers]
        ),
        input_binding_mean=_mean([item.input_binding for item in verifiers]),
        artifact_binding_mean=_mean([item.artifact_binding for item in verifiers]),
        protocol_compliance_mean=_mean(
            [item.protocol_compliance for item in verifiers]
        ),
        reward_mean=_mean([item.reward for item in verifiers]),
        verifier_result_count=len(verifiers),
        accepted_count=sum(item.reward == 1.0 for item in verifiers),
        false_certification_count=sum(item.false_certification for item in verifiers),
        exact_token_run_count=len(exact_tokens),
        total_tokens=sum(exact_tokens) if len(exact_tokens) == len(records) else None,
        exact_wall_run_count=len(exact_wall),
        wall_seconds=sum(exact_wall) if len(exact_wall) == len(records) else None,
        mcp_calls=sum(record.calls.mcp_calls for record in records),
        shell_calls=sum(record.calls.shell_calls for record in records),
        discovery_calls=sum(record.calls.discovery_calls for record in records),
        invocation_calls=sum(record.calls.invocation_calls for record in records),
        schema_valid_calls=sum(record.calls.schema_valid_calls for record in records),
        executable_calls=sum(record.calls.executable_calls for record in records),
        failed_calls=sum(record.calls.failed_calls for record in records),
        repeated_calls=sum(record.calls.repeated_calls for record in records),
        task_irrelevant_calls=sum(
            record.calls.task_irrelevant_calls for record in records
        ),
        producer_calls=sum(record.calls.producer_calls for record in records),
        checker_calls=sum(record.calls.checker_calls for record in records),
        candidate_or_witness_productions=sum(
            record.calls.candidate_or_witness_productions for record in records
        ),
        missing_applicable_checker=sum(
            record.calls.missing_applicable_checker for record in records
        ),
        recovered_calls=sum(record.calls.recovered_calls for record in records),
        timeout_count=sum(record.search_outcomes.timeout_count for record in records),
        cancellation_count=sum(
            record.search_outcomes.cancellation_count for record in records
        ),
        incomplete_search_count=sum(
            record.search_outcomes.incomplete_count for record in records
        ),
        bounded_exhaustion_count=sum(
            record.search_outcomes.bounded_exhaustion_count for record in records
        ),
        unresolved_nonconclusive_count=sum(
            record.search_outcomes.unresolved_nonconclusive_count for record in records
        ),
        improper_escalation_run_count=sum(
            record.search_outcomes.final_claim_improperly_escalates
            for record in records
        ),
        created_artifact_uri_count=sum(
            len(record.artifact_flow.created_uris) for record in records
        ),
        artifact_handoff_count=sum(
            record.artifact_flow.handoff_count for record in records
        ),
        reused_artifact_uri_count=sum(
            record.artifact_flow.reused_uri_count for record in records
        ),
        stale_binding_failure_count=sum(
            record.artifact_flow.stale_binding_failure_count for record in records
        ),
        substitution_failure_count=sum(
            record.artifact_flow.substitution_failure_count for record in records
        ),
        reasoning_required_run_count=sum(
            record.reasoning_protocol.mode == "REQUIRED" for record in records
        ),
        reasoning_complete_run_count=sum(
            record.reasoning_protocol.compliance == "COMPLETE" for record in records
        ),
        reasoning_incomplete_run_count=sum(
            record.reasoning_protocol.compliance == "INCOMPLETE" for record in records
        ),
        reasoning_log_entries=sum(
            record.reasoning_protocol.log_entries for record in records
        ),
        reasoning_log_bytes=sum(
            record.reasoning_protocol.log_bytes for record in records
        ),
        exact_reasoning_overhead_run_count=len(reasoning_overhead),
        reasoning_overhead_tokens=(
            sum(reasoning_overhead) if len(reasoning_overhead) == len(records) else None
        ),
        protocol_violation_count=sum(
            len(record.classification.protocol_violations) for record in records
        ),
        audit_classifications=dict(sorted(audit_counts.items())),
    )


def _aggregate(records: Sequence[RunTelemetry]) -> AggregateTables:
    per_task: list[AggregateRow] = []
    for task_id in sorted({record.task_id for record in records}):
        for condition in CONDITIONS:
            selected = [
                record
                for record in records
                if record.task_id == task_id and record.condition == condition
            ]
            if selected:
                per_task.append(_aggregate_row(task_id, condition, selected))
    overall: list[AggregateRow] = []
    for condition in CONDITIONS:
        selected = [record for record in records if record.condition == condition]
        if selected:
            overall.append(_aggregate_row("ALL", condition, selected))
    overall.append(_aggregate_row("ALL", "ALL", list(records)))
    return AggregateTables(per_task=per_task, overall=overall)


def build_bundle(roots: Sequence[Path]) -> TelemetryBundle:
    if not roots:
        raise TrajectoryTelemetryError("at least one run root is required")
    records = [
        record for root in roots for record in analyze_run(root.resolve(strict=True))
    ]
    records.sort(key=lambda item: (item.task_id, item.snapshot_id, item.condition))
    identities = [(item.snapshot_id, item.condition) for item in records]
    if len(identities) != len(set(identities)):
        raise TrajectoryTelemetryError("duplicate snapshot/condition input")
    return TelemetryBundle(
        schema_version="1",
        evidence_class="host-local-workflow-observation",
        causal_claim_authorized=False,
        records=records,
        aggregates=_aggregate(records),
    )


def _format_metric(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.3f}"


def render_tables(bundle: TelemetryBundle) -> str:
    def score_table(title: str, rows: Sequence[AggregateRow]) -> list[str]:
        lines = [
            f"## {title}: verifier and resources",
            "",
            "| Task | Condition | Runs | Infra | Verifiers | Correctness | Evidence | Scope | Assurance | Input bind | Artifact bind | Protocol | Reward | Accepted | False cert | Tokens | Wall s |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in rows:
            tokens = (
                str(row.total_tokens) if row.total_tokens is not None else "unavailable"
            )
            wall = (
                f"{row.wall_seconds:.3f}"
                if row.wall_seconds is not None
                else "unavailable"
            )
            lines.append(
                f"| {row.task_id} | {row.condition} | {row.run_count} | {row.infrastructure_complete} | "
                f"{row.verifier_result_count} | "
                f"{_format_metric(row.correctness_mean)} | {_format_metric(row.evidence_validity_mean)} | "
                f"{_format_metric(row.scope_accuracy_mean)} | {_format_metric(row.assurance_calibration_mean)} | "
                f"{_format_metric(row.input_binding_mean)} | {_format_metric(row.artifact_binding_mean)} | "
                f"{_format_metric(row.protocol_compliance_mean)} | {_format_metric(row.reward_mean)} | "
                f"{row.accepted_count} | {row.false_certification_count} | {tokens} | {wall} |"
            )
        return lines

    def call_table(title: str, rows: Sequence[AggregateRow]) -> list[str]:
        lines = [
            f"## {title}: calls",
            "",
            "| Task | Condition | Discovery | Invoke | Schema-valid | Executable | Failed | Repeated | Irrelevant | Producer | Checker | Produced | Missing checker | Recovered | MCP | Shell |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in rows:
            lines.append(
                f"| {row.task_id} | {row.condition} | {row.discovery_calls} | {row.invocation_calls} | "
                f"{row.schema_valid_calls} | {row.executable_calls} | {row.failed_calls} | "
                f"{row.repeated_calls} | {row.task_irrelevant_calls} | {row.producer_calls} | "
                f"{row.checker_calls} | {row.candidate_or_witness_productions} | "
                f"{row.missing_applicable_checker} | {row.recovered_calls} | "
                f"{row.mcp_calls} | {row.shell_calls} |"
            )
        return lines

    def workflow_table(title: str, rows: Sequence[AggregateRow]) -> list[str]:
        lines = [
            f"## {title}: search, artifacts, reasoning, and audit",
            "",
            "| Task | Condition | Timeout | Cancelled | Incomplete | Bounded exhausted | Unresolved | Overclaim runs | Created | Handoffs | Reused | Stale | Substituted | Reason req | Reason complete | Reason incomplete | Log entries | Log bytes | Violations | Audit classes |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for row in rows:
            audit = json.dumps(
                row.audit_classifications,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            lines.append(
                f"| {row.task_id} | {row.condition} | {row.timeout_count} | {row.cancellation_count} | "
                f"{row.incomplete_search_count} | {row.bounded_exhaustion_count} | "
                f"{row.unresolved_nonconclusive_count} | {row.improper_escalation_run_count} | "
                f"{row.created_artifact_uri_count} | {row.artifact_handoff_count} | "
                f"{row.reused_artifact_uri_count} | {row.stale_binding_failure_count} | "
                f"{row.substitution_failure_count} | {row.reasoning_required_run_count} | "
                f"{row.reasoning_complete_run_count} | {row.reasoning_incomplete_run_count} | "
                f"{row.reasoning_log_entries} | {row.reasoning_log_bytes} | "
                f"{row.protocol_violation_count} | `{audit}` |"
            )
        return lines

    def tables(title: str, rows: Sequence[AggregateRow]) -> list[str]:
        return [
            *score_table(title, rows),
            "",
            *call_table(title, rows),
            "",
            *workflow_table(title, rows),
        ]

    return "\n".join(
        [
            "# Symbolic coordination trajectory telemetry",
            "",
            "Descriptive host-local workflow observation; no causal claim is authorized.",
            "",
            *tables("Per task", bundle.aggregates.per_task),
            "",
            *tables("Overall", bundle.aggregates.overall),
            "",
        ]
    )


def _write_exclusive(path: Path, value: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise TrajectoryTelemetryError(f"refusing to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(value)


def emit(
    roots: Sequence[Path], output: Path, markdown_output: Path | None
) -> TelemetryBundle:
    bundle = build_bundle(roots)
    markdown = markdown_output or output.with_suffix(".md")
    if output.absolute() == markdown.absolute():
        raise TrajectoryTelemetryError("JSON and Markdown outputs must be distinct")
    for path in (output, markdown):
        if path.exists() or path.is_symlink():
            raise TrajectoryTelemetryError(f"refusing to overwrite output: {path}")
    _write_exclusive(output, _canonical_bytes(bundle.model_dump(mode="json")))
    _write_exclusive(markdown, render_tables(bundle).encode("utf-8"))
    return bundle


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify and emit symbolic trajectory telemetry"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    emit_parser = subparsers.add_parser("emit")
    emit_parser.add_argument("runs", nargs="+", type=Path)
    emit_parser.add_argument("--output", required=True, type=Path)
    emit_parser.add_argument("--markdown-output", type=Path)
    schema_parser = subparsers.add_parser("schema")
    schema_parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "schema":
            payload = _canonical_bytes(TelemetryBundle.model_json_schema())
            if args.output is None:
                sys.stdout.buffer.write(payload)
            else:
                _write_exclusive(args.output, payload)
            return 0
        bundle = emit(args.runs, args.output, args.markdown_output)
        print(render_tables(bundle), end="")
        print(f"JSON: {args.output}")
        print(f"Markdown: {args.markdown_output or args.output.with_suffix('.md')}")
        return 0
    except (OSError, ValidationError, TrajectoryTelemetryError, ValueError) as exc:
        print(f"symbolic trajectory telemetry: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
