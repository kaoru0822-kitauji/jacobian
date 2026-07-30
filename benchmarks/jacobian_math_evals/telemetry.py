"""Observable ATIF/Jacobian process metrics; never hidden reasoning."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

EVENT_KINDS = frozenset(
    {
        "capability.discovery",
        "capability.describe",
        "capability.invoke",
        "capability.parameter_error",
        "artifact.produced",
        "artifact.consumed",
        "verification.record",
        "shell.command",
        "file.read",
        "file.write",
        "trial.completed",
        "trial.timeout",
    }
)


@dataclass(frozen=True)
class ProcessSummary:
    event_counts: dict[str, int]
    repeated_invocations: int
    parameter_errors: int
    artifact_handoffs: int
    elapsed_seconds: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    completion_state: str
    false_certification: bool
    bounded_search_overclaim: bool
    scope_error: bool
    evidence_mismatch: bool


def summarize_events(
    events: list[dict[str, Any]],
    *,
    outcome: dict[str, Any],
) -> ProcessSummary:
    counts = Counter(
        event["kind"]
        for event in events
        if isinstance(event, dict) and event.get("kind") in EVENT_KINDS
    )
    invocations = [
        (
            event.get("capability_id"),
            event.get("arguments_digest"),
        )
        for event in events
        if event.get("kind") == "capability.invoke"
    ]
    repeated = len(invocations) - len(set(invocations))
    produced = {
        event.get("artifact_uri")
        for event in events
        if event.get("kind") == "artifact.produced"
    }
    consumed = {
        event.get("artifact_uri")
        for event in events
        if event.get("kind") in {"artifact.consumed", "verification.record"}
    }
    return ProcessSummary(
        event_counts=dict(sorted(counts.items())),
        repeated_invocations=repeated,
        parameter_errors=counts["capability.parameter_error"],
        artifact_handoffs=len((produced & consumed) - {None}),
        elapsed_seconds=float(outcome.get("elapsed_seconds", 0)),
        input_tokens=int(outcome.get("input_tokens", 0)),
        output_tokens=int(outcome.get("output_tokens", 0)),
        cost_usd=float(outcome.get("cost_usd", 0)),
        completion_state=str(outcome.get("completion_state", "UNKNOWN")),
        false_certification=bool(outcome.get("false_certification", False)),
        bounded_search_overclaim=bool(outcome.get("bounded_search_overclaim", False)),
        scope_error=bool(outcome.get("scope_error", False)),
        evidence_mismatch=bool(outcome.get("evidence_mismatch", False)),
    )
