from __future__ import annotations

import sqlite3

import pytest
from tests.component.workspaces._workspace_support import _open

from jacobian.contracts.workspaces import (
    WorkspaceCardState,
    WorkspaceFindingDraft,
    WorkspaceFindingKind,
    WorkspaceMarkDraft,
    WorkspaceQueryRequest,
    WorkspaceQueryView,
    WorkspaceWriteRequest,
)
from jacobian.workspaces import (
    WorkspaceReferenceError,
)


def test_workspace_invalid_marks_leave_no_partial_state(
    attached_complete_runtime,
) -> None:
    opened = _open(attached_complete_runtime, key="workspace-open-invalid-mark-001")
    seeded = attached_complete_runtime.core.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-invalid-mark-seed-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=opened.revision_id,
            findings=(
                WorkspaceFindingDraft(
                    client_ref="A1",
                    kind=WorkspaceFindingKind.ASSUMPTION,
                    title="First assumption",
                    body="First assumption body.",
                ),
                WorkspaceFindingDraft(
                    client_ref="A2",
                    kind=WorkspaceFindingKind.ASSUMPTION,
                    title="Second assumption",
                    body="Second assumption body.",
                ),
            ),
        )
    )

    invalid_requests = (
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-invalid-close-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=seeded.revision_id,
            marks=(
                WorkspaceMarkDraft(
                    client_ref="M1",
                    target_ref=seeded.id_map["A1"],
                    state=WorkspaceCardState.CLOSED,
                    reason="An assumption is not an open task.",
                ),
            ),
        ),
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-invalid-self-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=seeded.revision_id,
            marks=(
                WorkspaceMarkDraft(
                    client_ref="M1",
                    target_ref=seeded.id_map["A1"],
                    state=WorkspaceCardState.SUPERSEDED,
                    superseded_by_ref=seeded.id_map["A1"],
                    reason="A card cannot replace itself.",
                ),
            ),
        ),
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-invalid-problem-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=seeded.revision_id,
            marks=(
                WorkspaceMarkDraft(
                    client_ref="M1",
                    target_ref=opened.problem_card_id,
                    state=WorkspaceCardState.RETRACTED,
                    reason="The canonical problem remains immutable.",
                ),
            ),
        ),
    )
    for invalid in invalid_requests:
        with pytest.raises(WorkspaceReferenceError):
            attached_complete_runtime.core.workspaces.write(invalid)

    accepted = attached_complete_runtime.core.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-valid-supersede-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=seeded.revision_id,
            marks=(
                WorkspaceMarkDraft(
                    client_ref="M1",
                    target_ref=seeded.id_map["A1"],
                    state=WorkspaceCardState.SUPERSEDED,
                    superseded_by_ref=seeded.id_map["A2"],
                    reason="Use the second assumption instead.",
                ),
            ),
        )
    )
    with pytest.raises(WorkspaceReferenceError, match=r"supersession.*cycle"):
        attached_complete_runtime.core.workspaces.write(
            WorkspaceWriteRequest(
                idempotency_key="workspace-write-invalid-cycle-001",
                workspace_id=opened.workspace_id,
                branch_id=opened.branch_id,
                base_revision=accepted.revision_id,
                marks=(
                    WorkspaceMarkDraft(
                        client_ref="M2",
                        target_ref=seeded.id_map["A2"],
                        state=WorkspaceCardState.SUPERSEDED,
                        superseded_by_ref=seeded.id_map["A1"],
                        reason="This would create a replacement cycle.",
                    ),
                ),
            )
        )

    with sqlite3.connect(attached_complete_runtime.core.store.db_path) as connection:
        revision_count = connection.execute(
            "SELECT COUNT(*) FROM workspace_revisions WHERE workspace_id = ?",
            (opened.workspace_id,),
        ).fetchone()[0]
        mark_count = connection.execute(
            "SELECT COUNT(*) FROM workspace_marks WHERE workspace_id = ?",
            (opened.workspace_id,),
        ).fetchone()[0]
    assert revision_count == 3
    assert mark_count == 1


def test_workspace_invalidating_mark_requires_explicit_reactivation(
    attached_complete_runtime,
) -> None:
    opened = _open(
        attached_complete_runtime, key="workspace-open-explicit-reactivation-001"
    )
    seeded = attached_complete_runtime.core.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-explicit-reactivation-seed-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=opened.revision_id,
            findings=(
                WorkspaceFindingDraft(
                    client_ref="A1",
                    kind=WorkspaceFindingKind.ASSUMPTION,
                    title="Withdrawn premise",
                    body="This premise will be explicitly reactivated later.",
                ),
                WorkspaceFindingDraft(
                    client_ref="C1",
                    kind=WorkspaceFindingKind.CLAIM,
                    title="Dependent note",
                    body="This note depends on the withdrawn premise.",
                    assumption_refs=("A1",),
                ),
            ),
        )
    )
    retracted = attached_complete_runtime.core.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-explicit-reactivation-retract-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=seeded.revision_id,
            marks=(
                WorkspaceMarkDraft(
                    client_ref="M1",
                    target_ref=seeded.id_map["A1"],
                    state=WorkspaceCardState.RETRACTED,
                    reason="Withdraw this premise.",
                ),
            ),
        )
    )

    with pytest.raises(
        WorkspaceReferenceError,
        match="must be marked ACTIVE before",
    ):
        attached_complete_runtime.core.workspaces.write(
            WorkspaceWriteRequest(
                idempotency_key="workspace-write-explicit-reactivation-bypass-001",
                workspace_id=opened.workspace_id,
                branch_id=opened.branch_id,
                base_revision=retracted.revision_id,
                marks=(
                    WorkspaceMarkDraft(
                        client_ref="M2",
                        target_ref=seeded.id_map["A1"],
                        state=WorkspaceCardState.ARCHIVED,
                        reason="Archiving must not silently erase the withdrawal.",
                    ),
                ),
            )
        )

    unchanged = attached_complete_runtime.core.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            view=WorkspaceQueryView.CONTEXT,
            target_card_id=seeded.id_map["C1"],
        )
    )
    assert unchanged.revision_id == retracted.revision_id
    assert unchanged.context is not None
    assert unchanged.context.target.stale_due_to_ids == (seeded.id_map["A1"],)
    assert unchanged.context.dependencies[0].state is WorkspaceCardState.RETRACTED


def test_workspace_archiving_is_organizational_not_invalidation(
    attached_complete_runtime,
) -> None:
    opened = _open(attached_complete_runtime, key="workspace-open-archive-001")
    seeded = attached_complete_runtime.core.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-archive-seed-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=opened.revision_id,
            findings=(
                WorkspaceFindingDraft(
                    client_ref="A1",
                    kind=WorkspaceFindingKind.ASSUMPTION,
                    title="Filed premise",
                    body="This premise remains usable when filed away.",
                ),
                WorkspaceFindingDraft(
                    client_ref="C1",
                    kind=WorkspaceFindingKind.CLAIM,
                    title="Dependent claim",
                    body="This depends on the filed premise.",
                    assumption_refs=("A1",),
                ),
            ),
        )
    )
    archived = attached_complete_runtime.core.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-archive-mark-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=seeded.revision_id,
            marks=(
                WorkspaceMarkDraft(
                    client_ref="M1",
                    target_ref=seeded.id_map["A1"],
                    state=WorkspaceCardState.ARCHIVED,
                    reason="File this premise away without withdrawing it.",
                ),
            ),
        )
    )

    context = attached_complete_runtime.core.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            revision_id=archived.revision_id,
            view=WorkspaceQueryView.CONTEXT,
            target_card_id=seeded.id_map["C1"],
        )
    )
    assert context.context is not None
    assert context.context.target.stale is False
    assert context.context.dependencies[0].state is WorkspaceCardState.ARCHIVED
