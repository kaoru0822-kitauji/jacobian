"""Durable agent-authored working state without mathematical promotion."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from jacobian.canonical import canonicalize_json, loads_strict_json
from jacobian.contracts.results import ContractModel
from jacobian.contracts.workspaces import (
    WorkspaceAttempt,
    WorkspaceAttemptSummary,
    WorkspaceCardState,
    WorkspaceFinding,
    WorkspaceItemSummary,
    WorkspaceMark,
    WorkspaceRevisionOperation,
    WorkspaceScratchEntry,
    WorkspaceScratchSummary,
)
from jacobian.workspaces.errors import WorkspaceError, WorkspaceReferenceError


def _dependency_postorder(
    findings: dict[str, WorkspaceFinding],
    starts: Iterable[str],
) -> tuple[str, ...]:
    """Return dependencies before dependents without using Python recursion."""

    state: dict[str, int] = {}
    ordered: list[str] = []
    for start in starts:
        if state.get(start) == 2:
            continue
        stack: list[tuple[str, bool]] = [(start, False)]
        while stack:
            card_id, expanded = stack.pop()
            current_state = state.get(card_id, 0)
            if expanded:
                if current_state == 1:
                    state[card_id] = 2
                    ordered.append(card_id)
                continue
            if current_state == 2:
                continue
            if current_state == 1:
                raise WorkspaceError("workspace dependency graph contains a cycle")
            finding = findings.get(card_id)
            if finding is None:
                raise WorkspaceError(
                    "workspace dependency graph cites an unknown finding"
                )
            state[card_id] = 1
            stack.append((card_id, True))
            references = sorted(
                {*finding.dependency_ids, *finding.assumption_ids},
                reverse=True,
            )
            for reference in references:
                reference_state = state.get(reference, 0)
                if reference_state == 1:
                    raise WorkspaceError("workspace dependency graph contains a cycle")
                if reference_state != 2:
                    stack.append((reference, False))
    return tuple(ordered)


def _reject_new_dependency_cycles(findings: list[WorkspaceFinding]) -> None:
    new_ids = {finding.card_id for finding in findings}
    graph = {
        finding.card_id: {
            dependency
            for dependency in (*finding.dependency_ids, *finding.assumption_ids)
            if dependency in new_ids
        }
        for finding in findings
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(card_id: str) -> None:
        if card_id in visiting:
            raise WorkspaceReferenceError("new workspace findings contain a cycle")
        if card_id in visited:
            return
        visiting.add(card_id)
        for dependency in graph[card_id]:
            visit(dependency)
        visiting.remove(card_id)
        visited.add(card_id)

    for card_id in graph:
        visit(card_id)


def _reject_supersession_cycles(
    current_marks: Iterable[WorkspaceMark],
    new_marks: Iterable[WorkspaceMark],
) -> None:
    graph: dict[str, str] = {}
    for mark in current_marks:
        if (
            mark.state is WorkspaceCardState.SUPERSEDED
            and mark.superseded_by_id is not None
        ):
            graph[mark.target_card_id] = mark.superseded_by_id
    for mark in new_marks:
        if (
            mark.state is WorkspaceCardState.SUPERSEDED
            and mark.superseded_by_id is not None
        ):
            graph[mark.target_card_id] = mark.superseded_by_id
        else:
            graph.pop(mark.target_card_id, None)

    state: dict[str, int] = {}
    for start in graph:
        if state.get(start) == 2:
            continue
        path: list[str] = []
        card_id = start
        while card_id in graph:
            current_state = state.get(card_id, 0)
            if current_state == 1:
                raise WorkspaceReferenceError(
                    "workspace supersession marks contain a cycle"
                )
            if current_state == 2:
                break
            state[card_id] = 1
            path.append(card_id)
            card_id = graph[card_id]
        for visited_card_id in path:
            state[visited_card_id] = 2


def _request_digest(
    operation: WorkspaceRevisionOperation,
    payload: dict[str, object],
) -> str:
    data = canonicalize_json(
        {
            "operation": operation.value,
            "request": payload,
        }
    )
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _opaque_id(kind: str) -> str:
    return f"{kind}://{uuid.uuid4().hex}"


def _now() -> datetime:
    return datetime.now(UTC)


def _model_from_json[ModelT: ContractModel](
    model_type: type[ModelT],
    payload: bytes,
) -> ModelT:
    return model_type.model_validate(loads_strict_json(payload))


def _finding_summary(
    finding: WorkspaceFinding,
    revision_artifact_uri: str,
    mark: WorkspaceMark | None,
    mark_revision_artifact_uri: str | None,
    stale_due_to_ids: tuple[str, ...],
) -> WorkspaceItemSummary:
    return WorkspaceItemSummary(
        card_id=finding.card_id,
        kind=finding.kind,
        title=finding.title,
        body_excerpt=_excerpt(finding.body, 1024),
        dependency_ids=finding.dependency_ids,
        assumption_ids=finding.assumption_ids,
        tags=finding.tags,
        state=mark.state if mark is not None else WorkspaceCardState.ACTIVE,
        state_reason=mark.reason if mark is not None else None,
        state_mark_id=mark.mark_id if mark is not None else None,
        superseded_by_id=mark.superseded_by_id if mark is not None else None,
        state_revision=mark.created_revision if mark is not None else None,
        state_revision_artifact_uri=mark_revision_artifact_uri,
        stale=bool(stale_due_to_ids),
        stale_due_to_ids=stale_due_to_ids,
        created_revision=finding.created_revision,
        created_revision_artifact_uri=revision_artifact_uri,
    )


def _attempt_summary(
    attempt: WorkspaceAttempt,
    revision_artifact_uri: str,
) -> WorkspaceAttemptSummary:
    return WorkspaceAttemptSummary(
        attempt_id=attempt.attempt_id,
        target_card_id=attempt.target_card_id,
        method=attempt.method,
        outcome=attempt.outcome,
        summary_excerpt=_excerpt(attempt.summary, 768),
        artifact_uris=attempt.artifact_uris,
        created_revision=attempt.created_revision,
        created_revision_artifact_uri=revision_artifact_uri,
    )


def _scratch_summary(
    entry: WorkspaceScratchEntry,
    revision_artifact_uri: str,
) -> WorkspaceScratchSummary:
    return WorkspaceScratchSummary(
        scratch_id=entry.scratch_id,
        body_excerpt=_excerpt(entry.body, 512),
        tags=entry.tags,
        created_revision=entry.created_revision,
        created_revision_artifact_uri=revision_artifact_uri,
    )


def _excerpt(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"
