"""Build a passive external record from agent messages and Jacobian telemetry.

The observer runs after an agent and verifier finish.  It never participates in
MCP dispatch, and it deliberately excludes prompts, tool arguments, tool
results, and ``reasoning_content``.  Server telemetry remains authoritative for
mathematical calls; agent messages are optional self-reports only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

_DIGEST_16_PATTERN = r"^(?:[0-9a-f]{16}|none)$"
_TRACE_DIGEST_PATTERN = r"^(?:[0-9a-f]{8}|none)$"
_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_TRIAL_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
_DECIMAL_PATTERN = r"^[0-9]+(?:\.[0-9]+)?$"
_SUMMARY_MAX_BYTES = 512

_SERVER_EVENT_START = re.compile(r"\bMCP (?:tool call|capability attempt)\b")
_TOOL_CALL = re.compile(
    r"\bMCP tool call tool=(math\.(?:find|run))\b"
    r".{0,512}?\bstatus=(success|error)\b"
    r".{0,512}?\brequest_digest=([0-9a-f]{16}|none)\b"
    r".{0,512}?\btrace_digest=([0-9a-f]{8}|none)\b"
    r".{0,512}?\btrace_source=([^\s]+)\b"
    r".{0,512}?\bduration_ms=([0-9]+(?:\.[0-9]+)?)\b"
    r".{0,512}?\bresponse_bytes=([0-9]+)\b"
    r".{0,512}?\bargument_digest=(sha256:(?:[0-9a-f]\s*){64})",
    re.DOTALL,
)
_CAPABILITY_ATTEMPT = re.compile(
    r"\bMCP capability attempt request_digest=([0-9a-f]{16}|none)\b"
    r".{0,512}?\btrace_digest=([0-9a-f]{8}|none)\b"
    r".{0,512}?\btrace_source=([^\s]+)\b"
    r".{0,512}?\bcapability_id=([^\s]+)\b"
    r".{0,512}?\bcapability_version=([^\s]+)\b"
    r".{0,512}?\bmode=([^\s]+)\b"
    r".{0,512}?\bexecution_status=([A-Z_]+)\b"
    r".{0,512}?\bassurance=([^\s]+)\b"
    r".{0,512}?\bdiagnostic_codes=([^\s]+)\b"
    r".{0,512}?\battempt_duration_ms=([0-9]+(?:\.[0-9]+)?)\b"
    r".{0,512}?\boperation_runtime_ms=([^\s]+)\b"
    r".{0,512}?\bresponse_bytes=([0-9]+)\b"
    r".{0,512}?\bargument_digest=(sha256:(?:[0-9a-f]\s*){64})",
    re.DOTALL,
)

_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\bBearer\s+[^\s,;]+"), "[REDACTED_BEARER]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"/(?:Users|home)/[^/\s]+"), "[REDACTED_HOME]"),
    (
        re.compile(r"/(?:private/)?tmp/[^\s)\]]+|/var/folders/[^\s)\]]+"),
        "[REDACTED_TEMP_PATH]",
    ),
)


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceBinding(_Contract):
    source_kind: Literal["AGENT_TRACE", "JACOBIAN_MCP_LOG"]
    source_name: str = Field(min_length=1, max_length=255)
    source_format: Literal["CODEX_JSONL", "ATIF_JSON", "JACOBIAN_MCP_LOG"]
    status: Literal["COMPLETE", "INCOMPLETE", "MISSING"]
    sha256: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    byte_count: int = Field(ge=0)


class ObserverDiagnostic(_Contract):
    code: Literal[
        "MISSING_AGENT_TRACE",
        "UNREADABLE_AGENT_TRACE",
        "MALFORMED_AGENT_TRACE",
        "MALFORMED_AGENT_TRACE_ENTRY",
        "MISSING_SERVER_LOG",
        "UNREADABLE_SERVER_LOG",
        "MALFORMED_SERVER_EVENT",
        "SOURCE_OUTSIDE_TRIAL_ROOT",
    ]
    source_kind: Literal["AGENT_TRACE", "JACOBIAN_MCP_LOG"]
    source_position: int | None = Field(default=None, ge=1)


class PrivacyPolicy(_Contract):
    summary_source: Literal["EXPLICIT_AGENT_MESSAGE_ONLY"] = (
        "EXPLICIT_AGENT_MESSAGE_ONLY"
    )
    summary_max_utf8_bytes: Literal[512] = _SUMMARY_MAX_BYTES
    excluded_fields: tuple[
        Literal[
            "PROMPTS",
            "REASONING_CONTENT",
            "TOOL_ARGUMENTS",
            "TOOL_RESULTS",
            "HIDDEN_CHAIN_OF_THOUGHT",
        ],
        ...,
    ] = (
        "PROMPTS",
        "REASONING_CONTENT",
        "TOOL_ARGUMENTS",
        "TOOL_RESULTS",
        "HIDDEN_CHAIN_OF_THOUGHT",
    )
    retention: Literal["OPERATOR_CONTROLLED_DERIVED_ARTIFACT"] = (
        "OPERATOR_CONTROLLED_DERIVED_ARTIFACT"
    )


class ExplicitSummary(_Contract):
    sequence: int = Field(ge=1)
    trial_id: str = Field(pattern=_TRIAL_ID_PATTERN)
    source_format: Literal["CODEX_JSONL", "ATIF_JSON"]
    source_position: int = Field(ge=1)
    text: str = Field(min_length=1)
    original_utf8_bytes: int = Field(ge=1)
    truncated: bool
    redaction_count: int = Field(ge=0)
    evidence_semantics: Literal["OPTIONAL_SELF_REPORT"] = "OPTIONAL_SELF_REPORT"


class ToolCallEvent(_Contract):
    kind: Literal["TOOL_CALL"] = "TOOL_CALL"
    sequence: int = Field(ge=1)
    trial_id: str = Field(pattern=_TRIAL_ID_PATTERN)
    tool: Literal["math.find", "math.run"]
    status: Literal["success", "error"]
    request_digest: str = Field(pattern=_DIGEST_16_PATTERN)
    trace_digest: str = Field(pattern=_TRACE_DIGEST_PATTERN)
    trace_source: str = Field(min_length=1)
    duration_ms: str = Field(pattern=_DECIMAL_PATTERN)
    response_bytes: int = Field(ge=0)
    argument_digest: str = Field(pattern=_SHA256_PATTERN)
    correlation: Literal["SERVER_REQUEST_DIGEST", "UNAVAILABLE"]


class CapabilityAttemptEvent(_Contract):
    kind: Literal["CAPABILITY_ATTEMPT"] = "CAPABILITY_ATTEMPT"
    sequence: int = Field(ge=1)
    trial_id: str = Field(pattern=_TRIAL_ID_PATTERN)
    request_digest: str = Field(pattern=_DIGEST_16_PATTERN)
    trace_digest: str = Field(pattern=_TRACE_DIGEST_PATTERN)
    trace_source: str = Field(min_length=1)
    capability_id: str = Field(min_length=1)
    capability_version: str = Field(min_length=1)
    mode: str = Field(min_length=1)
    execution_status: str = Field(min_length=1)
    assurance: str = Field(min_length=1)
    diagnostic_codes: tuple[str, ...]
    attempt_duration_ms: str = Field(pattern=_DECIMAL_PATTERN)
    operation_runtime_ms: str | None
    response_bytes: int = Field(ge=0)
    argument_digest: str = Field(pattern=_SHA256_PATTERN)
    correlation: Literal["SERVER_REQUEST_DIGEST", "UNAVAILABLE"]


ServerEvent = Annotated[
    ToolCallEvent | CapabilityAttemptEvent,
    Field(discriminator="kind"),
]


class ObserverMetrics(_Contract):
    server_event_candidates: int = Field(ge=0)
    server_events_recorded: int = Field(ge=0)
    server_event_coverage: float = Field(ge=0.0, le=1.0)
    tool_calls_recorded: int = Field(ge=0)
    capability_attempts_recorded: int = Field(ge=0)
    explicit_summaries_recorded: int = Field(ge=0)


class ExternalReasoningObservation(_Contract):
    schema_version: Literal["1"] = "1"
    observer_id: Literal["jacobian.external-reasoning-observer"] = (
        "jacobian.external-reasoning-observer"
    )
    status: Literal["COMPLETE", "INCOMPLETE"]
    trial_id: str = Field(pattern=_TRIAL_ID_PATTERN)
    evidence_class: Literal["SERVER_OBSERVATION_WITH_OPTIONAL_SELF_REPORT"] = (
        "SERVER_OBSERVATION_WITH_OPTIONAL_SELF_REPORT"
    )
    causal_claim_authorized: Literal[False] = False
    affects_mathematical_assurance: Literal[False] = False
    sources: tuple[SourceBinding, SourceBinding]
    privacy: PrivacyPolicy
    explicit_summaries: tuple[ExplicitSummary, ...]
    server_events: tuple[ServerEvent, ...]
    metrics: ObserverMetrics
    diagnostics: tuple[ObserverDiagnostic, ...]


def _sha256(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _read_source(
    path: Path,
    *,
    kind: Literal["AGENT_TRACE", "JACOBIAN_MCP_LOG"],
    source_format: Literal["CODEX_JSONL", "ATIF_JSON", "JACOBIAN_MCP_LOG"],
) -> tuple[bytes | None, SourceBinding, ObserverDiagnostic | None]:
    missing_code = (
        "MISSING_AGENT_TRACE" if kind == "AGENT_TRACE" else "MISSING_SERVER_LOG"
    )
    unreadable_code = (
        "UNREADABLE_AGENT_TRACE" if kind == "AGENT_TRACE" else "UNREADABLE_SERVER_LOG"
    )
    if not path.is_file():
        return (
            None,
            SourceBinding(
                source_kind=kind,
                source_name=path.name or "missing",
                source_format=source_format,
                status="MISSING",
                byte_count=0,
            ),
            ObserverDiagnostic(code=missing_code, source_kind=kind),
        )
    try:
        content = path.read_bytes()
        content.decode("utf-8")
    except (OSError, UnicodeError):
        return (
            None,
            SourceBinding(
                source_kind=kind,
                source_name=path.name,
                source_format=source_format,
                status="INCOMPLETE",
                byte_count=0,
            ),
            ObserverDiagnostic(code=unreadable_code, source_kind=kind),
        )
    return (
        content,
        SourceBinding(
            source_kind=kind,
            source_name=path.name,
            source_format=source_format,
            status="COMPLETE",
            sha256=_sha256(content),
            byte_count=len(content),
        ),
        None,
    )


def _source_is_within_trial_root(path: Path, trial_root: Path) -> bool:
    try:
        relative = path.relative_to(trial_root)
    except ValueError:
        return False
    if not relative.parts:
        return False
    current = trial_root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return False
    try:
        path.resolve().relative_to(trial_root.resolve())
    except ValueError:
        return False
    return True


def _outside_trial_binding(
    path: Path,
    *,
    kind: Literal["AGENT_TRACE", "JACOBIAN_MCP_LOG"],
    source_format: Literal["CODEX_JSONL", "ATIF_JSON", "JACOBIAN_MCP_LOG"],
) -> tuple[None, SourceBinding, ObserverDiagnostic]:
    return (
        None,
        SourceBinding(
            source_kind=kind,
            source_name=path.name or "outside-trial-root",
            source_format=source_format,
            status="INCOMPLETE",
            byte_count=0,
        ),
        ObserverDiagnostic(
            code="SOURCE_OUTSIDE_TRIAL_ROOT",
            source_kind=kind,
        ),
    )


def _bounded_summary(text: str) -> tuple[str, int, bool, int]:
    redaction_count = 0
    redacted = text.strip()
    for pattern, replacement in _REDACTIONS:
        redacted, count = pattern.subn(replacement, redacted)
        redaction_count += count
    encoded = redacted.encode("utf-8")
    original_bytes = len(encoded)
    if original_bytes <= _SUMMARY_MAX_BYTES:
        return redacted, original_bytes, False, redaction_count
    bounded = encoded[:_SUMMARY_MAX_BYTES].decode("utf-8", errors="ignore")
    return bounded, original_bytes, True, redaction_count


def _summary(
    *,
    sequence: int,
    trial_id: str,
    source_format: Literal["CODEX_JSONL", "ATIF_JSON"],
    source_position: int,
    text: str,
) -> ExplicitSummary | None:
    if not text.strip():
        return None
    bounded, original_bytes, truncated, redactions = _bounded_summary(text)
    if not bounded:
        return None
    return ExplicitSummary(
        sequence=sequence,
        trial_id=trial_id,
        source_format=source_format,
        source_position=source_position,
        text=bounded,
        original_utf8_bytes=original_bytes,
        truncated=truncated,
        redaction_count=redactions,
    )


def _parse_codex_jsonl(
    text: str,
    *,
    trial_id: str,
) -> tuple[list[ExplicitSummary], list[ObserverDiagnostic]]:
    summaries: list[ExplicitSummary] = []
    diagnostics: list[ObserverDiagnostic] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            diagnostics.append(
                ObserverDiagnostic(
                    code="MALFORMED_AGENT_TRACE_ENTRY",
                    source_kind="AGENT_TRACE",
                    source_position=line_number,
                )
            )
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if not (
            isinstance(event, dict)
            and event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "agent_message"
            and isinstance(item.get("text"), str)
        ):
            continue
        value = _summary(
            sequence=len(summaries) + 1,
            trial_id=trial_id,
            source_format="CODEX_JSONL",
            source_position=line_number,
            text=item["text"],
        )
        if value is not None:
            summaries.append(value)
    return summaries, diagnostics


def _atif_message_text(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return None
    parts = [
        item["text"]
        for item in value
        if isinstance(item, dict)
        and item.get("type") == "text"
        and isinstance(item.get("text"), str)
    ]
    return "\n".join(parts)


def _parse_atif(
    text: str,
    *,
    trial_id: str,
) -> tuple[list[ExplicitSummary], list[ObserverDiagnostic]]:
    try:
        trajectory = json.loads(text)
    except json.JSONDecodeError:
        return [], [
            ObserverDiagnostic(
                code="MALFORMED_AGENT_TRACE",
                source_kind="AGENT_TRACE",
            )
        ]
    if not isinstance(trajectory, dict) or not isinstance(
        trajectory.get("steps"), list
    ):
        return [], [
            ObserverDiagnostic(
                code="MALFORMED_AGENT_TRACE",
                source_kind="AGENT_TRACE",
            )
        ]
    summaries: list[ExplicitSummary] = []
    for position, step in enumerate(trajectory["steps"], start=1):
        if not (
            isinstance(step, dict)
            and step.get("source") == "agent"
            and step.get("is_copied_context") is not True
        ):
            continue
        text_value = _atif_message_text(step.get("message"))
        if text_value is None:
            continue
        step_id = step.get("step_id")
        source_position = (
            step_id
            if isinstance(step_id, int)
            and not isinstance(step_id, bool)
            and step_id > 0
            else position
        )
        value = _summary(
            sequence=len(summaries) + 1,
            trial_id=trial_id,
            source_format="ATIF_JSON",
            source_position=source_position,
            text=text_value,
        )
        if value is not None:
            summaries.append(value)
    return summaries, []


def _correlation(
    request_digest: str,
) -> Literal["SERVER_REQUEST_DIGEST", "UNAVAILABLE"]:
    return "UNAVAILABLE" if request_digest == "none" else "SERVER_REQUEST_DIGEST"


def _tool_call_event(
    match: re.Match[str],
    *,
    sequence: int,
    trial_id: str,
) -> ToolCallEvent:
    (
        tool,
        status,
        request_digest,
        trace_digest,
        trace_source,
        duration_ms,
        response_bytes,
        argument_digest,
    ) = match.groups()
    return ToolCallEvent(
        sequence=sequence,
        trial_id=trial_id,
        tool=tool,
        status=status,
        request_digest=request_digest,
        trace_digest=trace_digest,
        trace_source=trace_source,
        duration_ms=duration_ms,
        response_bytes=int(response_bytes),
        argument_digest=re.sub(r"\s", "", argument_digest),
        correlation=_correlation(request_digest),
    )


def _capability_attempt_event(
    match: re.Match[str],
    *,
    sequence: int,
    trial_id: str,
) -> CapabilityAttemptEvent:
    (
        request_digest,
        trace_digest,
        trace_source,
        capability_id,
        capability_version,
        mode,
        execution_status,
        assurance,
        diagnostic_codes,
        attempt_duration_ms,
        operation_runtime_ms,
        response_bytes,
        argument_digest,
    ) = match.groups()
    return CapabilityAttemptEvent(
        sequence=sequence,
        trial_id=trial_id,
        request_digest=request_digest,
        trace_digest=trace_digest,
        trace_source=trace_source,
        capability_id=capability_id,
        capability_version=capability_version,
        mode=mode,
        execution_status=execution_status,
        assurance=assurance,
        diagnostic_codes=(
            () if diagnostic_codes == "none" else tuple(diagnostic_codes.split(","))
        ),
        attempt_duration_ms=attempt_duration_ms,
        operation_runtime_ms=(
            None if operation_runtime_ms == "none" else operation_runtime_ms
        ),
        response_bytes=int(response_bytes),
        argument_digest=re.sub(r"\s", "", argument_digest),
        correlation=_correlation(request_digest),
    )


def _parse_server_events(
    text: str,
    *,
    trial_id: str,
) -> tuple[list[ToolCallEvent | CapabilityAttemptEvent], int]:
    starts = list(_SERVER_EVENT_START.finditer(text))
    events: list[ToolCallEvent | CapabilityAttemptEvent] = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        segment = text[start.start() : end]
        tool_match = _TOOL_CALL.search(segment)
        attempt_match = _CAPABILITY_ATTEMPT.search(segment)
        if tool_match is not None:
            events.append(
                _tool_call_event(
                    tool_match,
                    sequence=len(events) + 1,
                    trial_id=trial_id,
                )
            )
        elif attempt_match is not None:
            events.append(
                _capability_attempt_event(
                    attempt_match,
                    sequence=len(events) + 1,
                    trial_id=trial_id,
                )
            )
    return events, len(starts)


def observe_external_reasoning(
    *,
    trial_id: str,
    trial_root: Path,
    agent_trace: Path,
    server_log: Path,
) -> ExternalReasoningObservation:
    """Return a fail-closed post-run observation without changing the run."""

    trace_format: Literal["CODEX_JSONL", "ATIF_JSON"] = (
        "CODEX_JSONL" if agent_trace.suffix == ".jsonl" else "ATIF_JSON"
    )
    trace_bytes, trace_binding, trace_read_diagnostic = (
        _read_source(
            agent_trace,
            kind="AGENT_TRACE",
            source_format=trace_format,
        )
        if _source_is_within_trial_root(agent_trace, trial_root)
        else _outside_trial_binding(
            agent_trace,
            kind="AGENT_TRACE",
            source_format=trace_format,
        )
    )
    server_bytes, server_binding, server_read_diagnostic = (
        _read_source(
            server_log,
            kind="JACOBIAN_MCP_LOG",
            source_format="JACOBIAN_MCP_LOG",
        )
        if _source_is_within_trial_root(server_log, trial_root)
        else _outside_trial_binding(
            server_log,
            kind="JACOBIAN_MCP_LOG",
            source_format="JACOBIAN_MCP_LOG",
        )
    )
    diagnostics = [
        item
        for item in (trace_read_diagnostic, server_read_diagnostic)
        if item is not None
    ]

    summaries: list[ExplicitSummary] = []
    if trace_bytes is not None:
        trace_text = trace_bytes.decode("utf-8")
        summaries, trace_diagnostics = (
            _parse_codex_jsonl(trace_text, trial_id=trial_id)
            if trace_format == "CODEX_JSONL"
            else _parse_atif(trace_text, trial_id=trial_id)
        )
        diagnostics.extend(trace_diagnostics)

    server_events: list[ToolCallEvent | CapabilityAttemptEvent] = []
    candidate_count = 0
    if server_bytes is not None:
        server_events, candidate_count = _parse_server_events(
            server_bytes.decode("utf-8"),
            trial_id=trial_id,
        )
        if len(server_events) != candidate_count:
            diagnostics.append(
                ObserverDiagnostic(
                    code="MALFORMED_SERVER_EVENT",
                    source_kind="JACOBIAN_MCP_LOG",
                )
            )

    trace_status = (
        "INCOMPLETE"
        if any(item.source_kind == "AGENT_TRACE" for item in diagnostics)
        else trace_binding.status
    )
    server_status = (
        "INCOMPLETE"
        if any(item.source_kind == "JACOBIAN_MCP_LOG" for item in diagnostics)
        else server_binding.status
    )
    trace_binding = trace_binding.model_copy(update={"status": trace_status})
    server_binding = server_binding.model_copy(update={"status": server_status})
    recorded = len(server_events)
    coverage = 1.0 if candidate_count == 0 else recorded / candidate_count
    return ExternalReasoningObservation(
        status="INCOMPLETE" if diagnostics else "COMPLETE",
        trial_id=trial_id,
        sources=(trace_binding, server_binding),
        privacy=PrivacyPolicy(),
        explicit_summaries=tuple(summaries),
        server_events=tuple(server_events),
        metrics=ObserverMetrics(
            server_event_candidates=candidate_count,
            server_events_recorded=recorded,
            server_event_coverage=coverage,
            tool_calls_recorded=sum(
                isinstance(item, ToolCallEvent) for item in server_events
            ),
            capability_attempts_recorded=sum(
                isinstance(item, CapabilityAttemptEvent) for item in server_events
            ),
            explicit_summaries_recorded=len(summaries),
        ),
        diagnostics=tuple(diagnostics),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial-id", required=True)
    parser.add_argument("--trial-root", type=Path, required=True)
    parser.add_argument("--agent-trace", type=Path, required=True)
    parser.add_argument("--server-log", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = observe_external_reasoning(
        trial_id=args.trial_id,
        trial_root=args.trial_root,
        agent_trace=args.agent_trace,
        server_log=args.server_log,
    )
    rendered = json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True)
    if args.output is None:
        print(rendered)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report.status == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CapabilityAttemptEvent",
    "ExplicitSummary",
    "ExternalReasoningObservation",
    "ObserverDiagnostic",
    "ObserverMetrics",
    "PrivacyPolicy",
    "SourceBinding",
    "ToolCallEvent",
    "observe_external_reasoning",
]
