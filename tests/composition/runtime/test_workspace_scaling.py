from __future__ import annotations

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


def test_workspace_context_handles_a_deep_dependency_chain(
    attached_complete_runtime,
) -> None:
    opened = _open(attached_complete_runtime, key="workspace-open-deep-context-001")
    revision_id = opened.revision_id
    previous_card_id: str | None = None

    for batch_index in range(16):
        findings = []
        for item_index in range(64):
            client_ref = f"N{item_index}"
            dependency_refs: tuple[str, ...]
            if item_index > 0:
                dependency_refs = (f"N{item_index - 1}",)
            elif previous_card_id is not None:
                dependency_refs = (previous_card_id,)
            else:
                dependency_refs = ()
            findings.append(
                WorkspaceFindingDraft(
                    client_ref=client_ref,
                    kind=WorkspaceFindingKind.FINDING,
                    title=f"Chain item {batch_index}-{item_index}",
                    body="One explicit link in a deliberately deep paper trail.",
                    dependency_refs=dependency_refs,
                )
            )
        written = attached_complete_runtime.core.workspaces.write(
            WorkspaceWriteRequest(
                idempotency_key=f"workspace-write-deep-{batch_index:03d}",
                workspace_id=opened.workspace_id,
                branch_id=opened.branch_id,
                base_revision=revision_id,
                findings=tuple(findings),
            )
        )
        revision_id = written.revision_id
        previous_card_id = written.id_map["N63"]

    assert previous_card_id is not None
    context = attached_complete_runtime.core.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            revision_id=revision_id,
            view=WorkspaceQueryView.CONTEXT,
            target_card_id=previous_card_id,
            limit=1,
        )
    )
    assert context.context is not None
    assert context.context.total_dependency_count == 1023
    assert context.context.truncated is True
    assert len(context.context.dependencies) == 1


def test_workspace_supersession_handles_a_deep_chain(attached_complete_runtime) -> None:
    opened = _open(
        attached_complete_runtime, key="workspace-open-deep-supersession-001"
    )
    revision_id = opened.revision_id
    card_ids: list[str] = []

    for batch_start in range(0, 1025, 64):
        drafts = tuple(
            WorkspaceFindingDraft(
                client_ref=f"N{index}",
                kind=WorkspaceFindingKind.FINDING,
                title=f"Replacement candidate {index}",
                body="One card in a deliberately deep replacement trail.",
            )
            for index in range(batch_start, min(batch_start + 64, 1025))
        )
        written = attached_complete_runtime.core.workspaces.write(
            WorkspaceWriteRequest(
                idempotency_key=(
                    f"workspace-write-deep-supersession-cards-{batch_start:04d}"
                ),
                workspace_id=opened.workspace_id,
                branch_id=opened.branch_id,
                base_revision=revision_id,
                findings=drafts,
            )
        )
        revision_id = written.revision_id
        card_ids.extend(written.id_map[draft.client_ref] for draft in drafts)

    for batch_start in range(0, 1024, 64):
        marks = tuple(
            WorkspaceMarkDraft(
                client_ref=f"M{index}",
                target_ref=card_ids[index],
                state=WorkspaceCardState.SUPERSEDED,
                reason="The next card replaces this exploratory note.",
                superseded_by_ref=card_ids[index + 1],
            )
            for index in range(batch_start, min(batch_start + 64, 1024))
        )
        written = attached_complete_runtime.core.workspaces.write(
            WorkspaceWriteRequest(
                idempotency_key=(
                    f"workspace-write-deep-supersession-marks-{batch_start:04d}"
                ),
                workspace_id=opened.workspace_id,
                branch_id=opened.branch_id,
                base_revision=revision_id,
                marks=marks,
            )
        )
        revision_id = written.revision_id

    context = attached_complete_runtime.core.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            revision_id=revision_id,
            view=WorkspaceQueryView.CONTEXT,
            target_card_id=card_ids[0],
        )
    )
    assert context.context is not None
    assert context.context.target.state is WorkspaceCardState.SUPERSEDED
    assert context.context.target.superseded_by_id == card_ids[1]


def test_workspace_context_truncation_and_stale_roots_are_deterministic(
    attached_complete_runtime,
) -> None:
    opened = _open(attached_complete_runtime, key="workspace-open-context-budget-001")
    seeded = attached_complete_runtime.core.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-context-budget-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=opened.revision_id,
            findings=(
                WorkspaceFindingDraft(
                    client_ref="A1",
                    kind=WorkspaceFindingKind.ASSUMPTION,
                    title="First premise",
                    body="First explicit premise.",
                ),
                WorkspaceFindingDraft(
                    client_ref="A2",
                    kind=WorkspaceFindingKind.ASSUMPTION,
                    title="Second premise",
                    body="Second explicit premise.",
                ),
                WorkspaceFindingDraft(
                    client_ref="C1",
                    kind=WorkspaceFindingKind.CLAIM,
                    title="First consequence",
                    body="Depends on the first premise.",
                    assumption_refs=("A1",),
                ),
                WorkspaceFindingDraft(
                    client_ref="C2",
                    kind=WorkspaceFindingKind.CLAIM,
                    title="Second consequence",
                    body="Depends on the second premise.",
                    assumption_refs=("A2",),
                ),
                WorkspaceFindingDraft(
                    client_ref="G1",
                    kind=WorkspaceFindingKind.GOAL,
                    title="Combined goal",
                    body="Depends on both consequences.",
                    dependency_refs=("C1", "C2"),
                ),
            ),
        )
    )
    marked = attached_complete_runtime.core.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-context-roots-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=seeded.revision_id,
            marks=(
                WorkspaceMarkDraft(
                    client_ref="M1",
                    target_ref=seeded.id_map["A1"],
                    state=WorkspaceCardState.RETRACTED,
                    reason="Withdraw the first premise.",
                ),
                WorkspaceMarkDraft(
                    client_ref="M2",
                    target_ref=seeded.id_map["A2"],
                    state=WorkspaceCardState.RETRACTED,
                    reason="Withdraw the second premise.",
                ),
            ),
        )
    )

    result = attached_complete_runtime.core.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            revision_id=marked.revision_id,
            view=WorkspaceQueryView.CONTEXT,
            target_card_id=seeded.id_map["G1"],
            limit=2,
        )
    )

    assert result.context is not None
    direct_claims = sorted((seeded.id_map["C1"], seeded.id_map["C2"]))
    assumption_for = {
        seeded.id_map["C1"]: seeded.id_map["A1"],
        seeded.id_map["C2"]: seeded.id_map["A2"],
    }
    full_order = [
        item
        for claim_id in direct_claims
        for item in (assumption_for[claim_id], claim_id)
    ]
    assert [item.card_id for item in result.context.dependencies] == full_order[:2]
    assert result.context.total_dependency_count == 4
    assert result.context.truncated is True
    assert result.context.target.stale_due_to_ids == tuple(
        sorted((seeded.id_map["A1"], seeded.id_map["A2"]))
    )
