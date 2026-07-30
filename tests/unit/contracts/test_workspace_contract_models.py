from __future__ import annotations

import pytest
from pydantic import ValidationError

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
    WorkspaceWriteRequest,
)


def test_workspace_drafts_do_not_accept_caller_controlled_verification() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        WorkspaceFindingDraft.model_validate(
            {
                "client_ref": "L1",
                "kind": "CLAIM",
                "title": "Forged",
                "body": "Caller attempts to self-promote this claim.",
                "verification": "VERIFIED",
            }
        )


def test_workspace_drafts_use_canonical_operational_values() -> None:
    goal = WorkspaceFindingDraft.model_validate(
        {
            "client_ref": "G1",
            "kind": "GOAL",
            "title": "Finish the proof",
            "body": "This remains agent-authored and unverified.",
        }
    )
    attempt = WorkspaceAttemptDraft.model_validate(
        {
            "client_ref": "T1",
            "target_ref": "G1",
            "method": "direct",
            "outcome": "COMPLETED",
            "summary": "The operational attempt finished.",
        }
    )
    mark = WorkspaceMarkDraft.model_validate(
        {
            "client_ref": "M1",
            "target_ref": "G1",
            "state": "CLOSED",
            "reason": "The agent explicitly closed this work item.",
        }
    )

    assert goal.kind is WorkspaceFindingKind.GOAL
    assert attempt.outcome is WorkspaceAttemptOutcome.COMPLETED
    assert mark.reason == "The agent explicitly closed this work item."
    assert goal.model_dump(mode="json")["kind"] == "GOAL"
    assert attempt.model_dump(mode="json")["outcome"] == "COMPLETED"
    assert set(mark.model_dump(mode="json")) == {
        "client_ref",
        "target_ref",
        "state",
        "reason",
        "superseded_by_ref",
    }


def test_workspace_finding_kind_accepts_a_generic_finding_card() -> None:
    finding = WorkspaceFindingDraft(
        client_ref="F1",
        kind="FINDING",
        title="Recorded observation",
        body="This is a generic agent-authored observation.",
    )

    assert finding.kind is WorkspaceFindingKind.FINDING


def test_workspace_focus_requires_an_explicit_update() -> None:
    with pytest.raises(
        ValidationError,
        match="focus update requires active_ref, pinned_refs, or clear=true",
    ):
        WorkspaceFocusDraft()

    with pytest.raises(
        ValidationError,
        match="focus clear cannot be combined",
    ):
        WorkspaceFocusDraft(active_ref="G1", clear=True)


def test_workspace_focus_rejects_attempt_and_scratch_client_refs() -> None:
    with pytest.raises(
        ValidationError,
        match="focus references must identify finding cards",
    ):
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-focus-kind-001",
            workspace_id="workspace://00000000000000000000000000000000",
            branch_id="branch://00000000000000000000000000000000",
            base_revision="revision://00000000000000000000000000000000",
            attempts=(
                WorkspaceAttemptDraft(
                    client_ref="T1",
                    target_ref="card://00000000000000000000000000000000",
                    method="direct",
                    outcome=WorkspaceAttemptOutcome.BLOCKED,
                    summary="This attempt cannot be focused directly.",
                ),
            ),
            focus=WorkspaceFocusDraft(pinned_refs=("T1",)),
        )


def test_workspace_mark_contracts_fail_closed() -> None:
    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        WorkspaceMarkDraft.model_validate(
            {
                "client_ref": "M1",
                "target_ref": "card://00000000000000000000000000000000",
                "state": "CLOSED",
                "reason": "Canonical reason.",
                "summary": "Conflicting alias.",
            }
        )

    with pytest.raises(
        ValidationError,
        match="SUPERSEDED marks require superseded_by_ref",
    ):
        WorkspaceMarkDraft(
            client_ref="M1",
            target_ref="card://00000000000000000000000000000000",
            state=WorkspaceCardState.SUPERSEDED,
            reason="Missing replacement.",
        )

    with pytest.raises(
        ValidationError,
        match="only SUPERSEDED marks may carry superseded_by_ref",
    ):
        WorkspaceMarkDraft(
            client_ref="M1",
            target_ref="card://00000000000000000000000000000000",
            state=WorkspaceCardState.ACTIVE,
            superseded_by_ref="card://11111111111111111111111111111111",
            reason="An active mark cannot silently replace a card.",
        )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        WorkspaceMarkDraft.model_validate(
            {
                "client_ref": "M1",
                "target_ref": "card://00000000000000000000000000000000",
                "state": "CLOSED",
                "reason": "Caller attempts to self-promote the mark.",
                "verification": "VERIFIED",
            }
        )

    with pytest.raises(
        ValidationError,
        match="target_card_id is required for the CONTEXT view",
    ):
        WorkspaceQueryRequest(
            workspace_id="workspace://00000000000000000000000000000000",
            branch_id="branch://00000000000000000000000000000000",
            view=WorkspaceQueryView.CONTEXT,
        )
