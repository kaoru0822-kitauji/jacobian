from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

import pytest
from tests.integration.infrastructure._workspace_support import _open

from jacobian.contracts.workspaces import (
    WorkspaceAttemptDraft,
    WorkspaceAttemptOutcome,
    WorkspaceCardState,
    WorkspaceFindingDraft,
    WorkspaceFindingKind,
    WorkspaceFocusDraft,
    WorkspaceMarkDraft,
    WorkspaceQueryRequest,
    WorkspaceQueryView,
    WorkspaceRevision,
    WorkspaceScratchDraft,
    WorkspaceWriteRequest,
)
from jacobian.kernel import JacobianKernel

pytestmark = pytest.mark.usefixtures("initialized_kernel_store")


def test_workspace_marks_close_goals_and_propagate_staleness(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    opened = _open(kernel, key="workspace-open-marks-001")
    seeded = kernel.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-mark-seed-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=opened.revision_id,
            findings=(
                WorkspaceFindingDraft(
                    client_ref="A1",
                    kind=WorkspaceFindingKind.ASSUMPTION,
                    title="Finite scope",
                    body="Only n <= 20 is in scope.",
                ),
                WorkspaceFindingDraft(
                    client_ref="C1",
                    kind=WorkspaceFindingKind.CLAIM,
                    title="Checked recurrence",
                    body="The recurrence held throughout the finite scope.",
                    assumption_refs=("A1",),
                ),
                WorkspaceFindingDraft(
                    client_ref="G1",
                    kind=WorkspaceFindingKind.GOAL,
                    title="Extend the recurrence",
                    body="Determine whether the recurrence extends beyond the sample.",
                    dependency_refs=("C1",),
                ),
            ),
            attempts=(
                WorkspaceAttemptDraft(
                    client_ref="T1",
                    target_ref="G1",
                    method="finite_enumeration",
                    outcome=WorkspaceAttemptOutcome.COMPLETED,
                    summary="The bounded enumeration completed.",
                ),
            ),
            focus=WorkspaceFocusDraft(active_ref="G1"),
        )
    )

    before_mark = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            view=WorkspaceQueryView.RESUME,
        )
    )
    assert before_mark.resume is not None
    assert [item.card_id for item in before_mark.resume.open_goals] == [
        seeded.id_map["G1"]
    ]

    retracted = kernel.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-mark-retract-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=seeded.revision_id,
            marks=(
                WorkspaceMarkDraft(
                    client_ref="M2",
                    target_ref=seeded.id_map["A1"],
                    state=WorkspaceCardState.RETRACTED,
                    reason="The finite scope was an exploratory restriction, not a premise.",
                ),
            ),
        )
    )

    after_retraction = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            revision_id=retracted.revision_id,
            view=WorkspaceQueryView.RESUME,
        )
    )
    assert after_retraction.resume is not None
    assert [item.card_id for item in after_retraction.resume.open_goals] == [
        seeded.id_map["G1"]
    ]
    assert after_retraction.resume.open_goals[0].stale is True
    stale_frontier = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            revision_id=retracted.revision_id,
            view=WorkspaceQueryView.FRONTIER,
        )
    )
    assert [item.goal.card_id for item in stale_frontier.frontier] == [
        seeded.id_map["G1"]
    ]

    marked = kernel.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-mark-close-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=retracted.revision_id,
            marks=(
                WorkspaceMarkDraft(
                    client_ref="M1",
                    target_ref=seeded.id_map["G1"],
                    state=WorkspaceCardState.CLOSED,
                    reason="The agent has no remaining work on this bounded subgoal.",
                ),
            ),
        )
    )

    assert retracted.marks_written == 1
    assert marked.marks_written == 1
    assert marked.id_map["M1"].startswith("mark://")
    retracted_revision = WorkspaceRevision.model_validate(
        kernel.store.get(retracted.revision_artifact_uri).payload
    )
    revision = WorkspaceRevision.model_validate(
        kernel.store.get(marked.revision_artifact_uri).payload
    )
    for stored_revision in (retracted_revision, revision):
        assert {mark.assertion for mark in stored_revision.marks} == {"AGENT_RECORDED"}
        assert {mark.verification for mark in stored_revision.marks} == {"UNVERIFIED"}

    resume = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            revision_id=marked.revision_id,
            view=WorkspaceQueryView.RESUME,
        )
    )
    assert resume.resume is not None
    assert resume.resume.open_goals == ()
    assert {item.card_id for item in resume.resume.stale_items} == {
        seeded.id_map["C1"],
        seeded.id_map["G1"],
    }
    assert resume.resume.active_item is not None
    assert resume.resume.active_item.state is WorkspaceCardState.CLOSED
    assert resume.resume.active_item.stale is True
    assert resume.resume.active_item.stale_due_to_ids == (seeded.id_map["A1"],)

    frontier = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            view=WorkspaceQueryView.FRONTIER,
        )
    )
    assert frontier.frontier == ()

    stale = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            view=WorkspaceQueryView.STALE,
        )
    )
    assert {item.card_id for item in stale.stale_items} == {
        seeded.id_map["C1"],
        seeded.id_map["G1"],
    }

    context = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            view=WorkspaceQueryView.CONTEXT,
            target_card_id=seeded.id_map["G1"],
        )
    )
    assert context.context is not None
    assert context.context.target.card_id == seeded.id_map["G1"]
    assert [item.card_id for item in context.context.dependencies] == [
        seeded.id_map["A1"],
        seeded.id_map["C1"],
    ]
    assert context.context.dependencies[0].state is WorkspaceCardState.RETRACTED
    assert context.context.total_dependency_count == 2
    assert context.context.truncated is False
    assert [attempt.attempt_id for attempt in context.context.recent_attempts] == [
        seeded.id_map["T1"]
    ]

    restarted = JacobianKernel(tmp_path)
    replayed = restarted.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            view=WorkspaceQueryView.CONTEXT,
            target_card_id=seeded.id_map["G1"],
        )
    )
    assert replayed == context


def test_workspace_supersession_and_reactivation_are_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path)
    opened = _open(kernel, key="workspace-open-supersede-001")
    seeded = kernel.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-supersede-seed-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=opened.revision_id,
            findings=(
                WorkspaceFindingDraft(
                    client_ref="A1",
                    kind=WorkspaceFindingKind.ASSUMPTION,
                    title="Original scope",
                    body="Assume n <= 20.",
                ),
                WorkspaceFindingDraft(
                    client_ref="C1",
                    kind=WorkspaceFindingKind.CLAIM,
                    title="Scope-dependent claim",
                    body="This card depends on the original scope.",
                    assumption_refs=("A1",),
                ),
            ),
        )
    )
    monkeypatch.setattr(
        "jacobian.workspaces._now",
        lambda: datetime(2030, 1, 1, tzinfo=UTC),
    )
    superseded = kernel.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-supersede-state-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=seeded.revision_id,
            findings=(
                WorkspaceFindingDraft(
                    client_ref="A2",
                    kind=WorkspaceFindingKind.ASSUMPTION,
                    title="Revised scope",
                    body="Assume n <= 50.",
                ),
            ),
            marks=(
                WorkspaceMarkDraft(
                    client_ref="M1",
                    target_ref=seeded.id_map["A1"],
                    state=WorkspaceCardState.SUPERSEDED,
                    superseded_by_ref="A2",
                    reason="Replace the exploratory bound with the revised scope.",
                ),
            ),
        )
    )

    context = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            view=WorkspaceQueryView.CONTEXT,
            target_card_id=seeded.id_map["C1"],
        )
    )
    assert context.context is not None
    original = context.context.dependencies[0]
    assert original.state is WorkspaceCardState.SUPERSEDED
    assert original.superseded_by_id == superseded.id_map["A2"]
    assert context.context.target.stale_due_to_ids == (seeded.id_map["A1"],)

    monkeypatch.setattr(
        "jacobian.workspaces._now",
        lambda: datetime(2020, 1, 1, tzinfo=UTC),
    )
    reactivated = kernel.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-reactivate-state-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=superseded.revision_id,
            marks=(
                WorkspaceMarkDraft(
                    client_ref="M2",
                    target_ref=seeded.id_map["A1"],
                    state=WorkspaceCardState.ACTIVE,
                    reason="Restore the original scope for a separate bounded argument.",
                ),
            ),
        )
    )
    after = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            revision_id=reactivated.revision_id,
            view=WorkspaceQueryView.CONTEXT,
            target_card_id=seeded.id_map["C1"],
        )
    )
    assert after.context is not None
    assert after.context.target.stale is False
    assert after.context.dependencies[0].state is WorkspaceCardState.ACTIVE
    assert after.context.dependencies[0].superseded_by_id is None


def test_workspace_query_uses_one_revision_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path)
    opened = _open(kernel, key="workspace-open-query-snapshot-001")
    projection_started = Event()
    continue_projection = Event()
    original_projection = kernel.workspaces._projection

    def paused_projection(
        connection: sqlite3.Connection,
        request: WorkspaceQueryRequest,
    ) -> object:
        projection_started.set()
        if not continue_projection.wait(timeout=10):
            raise AssertionError("test did not release the paused projection")
        return original_projection(connection, request)

    monkeypatch.setattr(kernel.workspaces, "_projection", paused_projection)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(
            kernel.workspaces.query,
            WorkspaceQueryRequest(
                workspace_id=opened.workspace_id,
                branch_id=opened.branch_id,
                revision_id=opened.revision_id,
                view=WorkspaceQueryView.RESUME,
            ),
        )
        assert projection_started.wait(timeout=10)
        advanced = kernel.workspaces.write(
            WorkspaceWriteRequest(
                idempotency_key="workspace-write-during-query-001",
                workspace_id=opened.workspace_id,
                branch_id=opened.branch_id,
                base_revision=opened.revision_id,
                findings=(
                    WorkspaceFindingDraft(
                        client_ref="G1",
                        kind=WorkspaceFindingKind.GOAL,
                        title="Concurrently appended goal",
                        body="This must not appear under the old revision handle.",
                    ),
                ),
            )
        )
        continue_projection.set()
        snapshotted = pending.result(timeout=10)

    assert snapshotted.revision_id == opened.revision_id
    assert snapshotted.resume is not None
    assert snapshotted.resume.open_goals == ()

    monkeypatch.setattr(kernel.workspaces, "_projection", original_projection)
    latest = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            revision_id=advanced.revision_id,
            view=WorkspaceQueryView.RESUME,
        )
    )
    assert latest.resume is not None
    assert [item.card_id for item in latest.resume.open_goals] == [
        advanced.id_map["G1"]
    ]


def test_workspace_recent_views_follow_acceptance_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kernel = JacobianKernel(tmp_path)
    opened = _open(kernel, key="workspace-open-acceptance-order-001")
    monkeypatch.setattr(
        "jacobian.workspaces._now",
        lambda: datetime(2030, 1, 1, tzinfo=UTC),
    )
    first = kernel.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-acceptance-order-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=opened.revision_id,
            scratch=(WorkspaceScratchDraft(client_ref="S1", body="Accepted first."),),
            findings=(
                WorkspaceFindingDraft(
                    client_ref="G1",
                    kind=WorkspaceFindingKind.GOAL,
                    title="Accepted first",
                    body="This write has a later wall-clock timestamp.",
                ),
            ),
            attempts=(
                WorkspaceAttemptDraft(
                    client_ref="T1",
                    target_ref="G1",
                    method="first",
                    outcome=WorkspaceAttemptOutcome.BLOCKED,
                    summary="Accepted first.",
                ),
            ),
        )
    )
    monkeypatch.setattr(
        "jacobian.workspaces._now",
        lambda: datetime(2020, 1, 1, tzinfo=UTC),
    )
    second = kernel.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-acceptance-order-002",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=first.revision_id,
            scratch=(WorkspaceScratchDraft(client_ref="S2", body="Accepted second."),),
            findings=(
                WorkspaceFindingDraft(
                    client_ref="G2",
                    kind=WorkspaceFindingKind.GOAL,
                    title="Accepted second",
                    body="This write has an earlier wall-clock timestamp.",
                ),
            ),
            attempts=(
                WorkspaceAttemptDraft(
                    client_ref="T2",
                    target_ref="G2",
                    method="second",
                    outcome=WorkspaceAttemptOutcome.BLOCKED,
                    summary="Accepted second.",
                ),
            ),
        )
    )

    resume = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            revision_id=second.revision_id,
            view=WorkspaceQueryView.RESUME,
        )
    )

    assert resume.resume is not None
    assert [item.card_id for item in resume.resume.open_goals] == [
        second.id_map["G2"],
        first.id_map["G1"],
    ]
    assert [item.attempt_id for item in resume.resume.recent_attempts] == [
        second.id_map["T2"],
        first.id_map["T1"],
    ]
    assert [item.scratch_id for item in resume.resume.recent_scratch] == [
        second.id_map["S2"],
        first.id_map["S1"],
    ]
