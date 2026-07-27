from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

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
    WorkspaceOpenRequest,
    WorkspaceOpenResult,
    WorkspaceQueryRequest,
    WorkspaceQueryView,
    WorkspaceRevision,
    WorkspaceScratchDraft,
    WorkspaceWriteRequest,
)
from jacobian.kernel import JacobianKernel
from jacobian.workspaces import (
    WorkspaceConflictError,
    WorkspaceIdempotencyError,
    WorkspaceReferenceError,
)

pytestmark = pytest.mark.usefixtures("initialized_kernel_store")


def _open(
    kernel: JacobianKernel,
    *,
    key: str = "workspace-open-001",
) -> WorkspaceOpenResult:
    return kernel.workspaces.open(
        WorkspaceOpenRequest(
            idempotency_key=key,
            name="bounded conjecture",
            problem="Determine whether P(n) holds for every n in the declared scope.",
            tags=("bounded",),
        )
    )


@pytest.mark.integration
def test_workspace_open_is_idempotent_and_restart_replays_revision(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    request = WorkspaceOpenRequest(
        idempotency_key="workspace-open-replay-001",
        name="replay fixture",
        problem="Prove or refute the fixture claim.",
    )

    first = kernel.workspaces.open(request)
    second = kernel.workspaces.open(request)

    assert second == first
    revision_artifact = kernel.store.get(first.revision_artifact_uri)
    revision = WorkspaceRevision.model_validate(revision_artifact.payload)
    assert revision.revision_id == first.revision_id
    assert revision.parent_revision is None
    assert revision.findings[0].card_id == first.problem_card_id
    assert revision.findings[0].verification == "UNVERIFIED"
    assert revision.focus is not None
    assert revision.focus.active_item_id == first.problem_card_id

    restarted = JacobianKernel(tmp_path)
    resume = restarted.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=first.workspace_id,
            branch_id=first.branch_id,
            view=WorkspaceQueryView.RESUME,
        )
    )

    assert resume.revision_id == first.revision_id
    assert resume.revision_artifact_uri == first.revision_artifact_uri
    assert resume.resume is not None
    assert resume.resume.problem.verification == "UNVERIFIED"
    assert "retrieval does not promote" in resume.warning


@pytest.mark.integration
def test_workspace_write_cannot_add_a_second_problem(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    opened = _open(kernel, key="workspace-open-single-problem-001")
    problem_draft = WorkspaceFindingDraft(
        client_ref="P2",
        kind=WorkspaceFindingKind.PROBLEM,
        title="Hidden second problem",
        body="A write must not create another canonical problem.",
    )

    with pytest.raises(
        ValidationError,
        match=r"only workspace\.open may create the canonical PROBLEM",
    ):
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-second-problem-contract-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=opened.revision_id,
            findings=(problem_draft,),
        )

    bypassed_contract = WorkspaceWriteRequest.model_construct(
        request_version="1",
        idempotency_key="workspace-write-second-problem-service-001",
        workspace_id=opened.workspace_id,
        branch_id=opened.branch_id,
        base_revision=opened.revision_id,
        scratch=(),
        findings=(problem_draft,),
        attempts=(),
        marks=(),
        focus=None,
    )
    with pytest.raises(
        ValidationError,
        match=r"only workspace\.open may create the canonical PROBLEM",
    ):
        kernel.workspaces.write(bypassed_contract)

    with (
        pytest.raises(
            WorkspaceReferenceError,
            match=r"only workspace\.open may create the canonical PROBLEM",
        ),
        kernel.workspaces._connect() as connection,
    ):
        kernel.workspaces._prepare_write(
            connection,
            bypassed_contract,
            "sha256:" + ("0" * 64),
        )

    resumed = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            view=WorkspaceQueryView.RESUME,
        )
    )
    assert resumed.revision_id == opened.revision_id
    assert resumed.resume is not None
    assert resumed.resume.problem.card_id == opened.problem_card_id


@pytest.mark.integration
def test_workspace_write_builds_resume_frontier_and_attempt_views(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    opened = _open(kernel)
    request = WorkspaceWriteRequest(
        idempotency_key="workspace-write-batch-001",
        workspace_id=opened.workspace_id,
        branch_id=opened.branch_id,
        base_revision=opened.revision_id,
        scratch=(
            WorkspaceScratchDraft(
                client_ref="S1",
                body="Try induction, but keep the boundary case separate.",
                tags=("induction",),
            ),
        ),
        findings=(
            WorkspaceFindingDraft(
                client_ref="A1",
                kind=WorkspaceFindingKind.ASSUMPTION,
                title="Finite scope",
                body="The current experiment only concerns n <= 20.",
            ),
            WorkspaceFindingDraft(
                client_ref="G1",
                kind=WorkspaceFindingKind.GOAL,
                title="Close the induction step",
                body="Find a strengthened hypothesis that controls the boundary term.",
                assumption_refs=("A1",),
                tags=("frontier",),
            ),
            WorkspaceFindingDraft(
                client_ref="L1",
                kind=WorkspaceFindingKind.CLAIM,
                title="Candidate recurrence",
                body="A stronger recurrence may suffice.",
                dependency_refs=("G1",),
            ),
        ),
        attempts=(
            WorkspaceAttemptDraft(
                client_ref="T1",
                target_ref="G1",
                method="ordinary_induction",
                outcome=WorkspaceAttemptOutcome.BLOCKED,
                summary="The step requires a bound not present in the hypothesis.",
            ),
        ),
        focus=WorkspaceFocusDraft(active_ref="G1", pinned_refs=("G1", "L1")),
    )

    written = kernel.workspaces.write(request)
    reused = kernel.workspaces.write(request)

    assert reused == written
    assert written.scratch_written == 1
    assert written.findings_written == 3
    assert written.attempts_written == 1
    assert set(written.unverified_finding_ids) == {
        written.id_map["A1"],
        written.id_map["G1"],
        written.id_map["L1"],
    }
    assert set(written.unresolved_dependency_ids) == {
        written.id_map["A1"],
        written.id_map["G1"],
    }
    assert "cannot establish an exact mathematical conclusion" in (
        written.assurance_notice
    )
    revision_artifact = kernel.store.get(written.revision_artifact_uri)
    assert opened.revision_artifact_uri in revision_artifact.manifest.parents
    revision = WorkspaceRevision.model_validate(revision_artifact.payload)
    assert revision.parent_revision == opened.revision_id
    assert {item.verification for item in revision.findings} == {"UNVERIFIED"}
    assert {item.verification for item in revision.attempts} == {"UNVERIFIED"}

    resume = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            view=WorkspaceQueryView.RESUME,
        )
    )
    assert resume.resume is not None
    assert resume.resume.active_item is not None
    assert resume.resume.active_item.card_id == written.id_map["G1"]
    assert (
        resume.resume.active_item.created_revision_artifact_uri
        == written.revision_artifact_uri
    )
    assert {item.card_id for item in resume.resume.pinned_items} == {
        written.id_map["G1"],
        written.id_map["L1"],
    }
    assert resume.resume.open_goals[0].assumption_ids == (written.id_map["A1"],)
    assert resume.resume.recent_attempts[0].verification == "UNVERIFIED"

    frontier = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            view=WorkspaceQueryView.FRONTIER,
        )
    )
    assert len(frontier.frontier) == 1
    assert frontier.frontier[0].attempt_count == 1
    assert frontier.frontier[0].last_attempt is not None
    assert frontier.frontier[0].last_attempt.outcome is WorkspaceAttemptOutcome.BLOCKED

    attempts = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            view=WorkspaceQueryView.ATTEMPTS,
            target_card_id=written.id_map["G1"],
        )
    )
    assert [item.attempt_id for item in attempts.attempts] == [written.id_map["T1"]]


@pytest.mark.integration
def test_workspace_rejects_stale_base_without_partial_index_writes(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    opened = _open(kernel)
    accepted = kernel.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-accepted-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=opened.revision_id,
            findings=(
                WorkspaceFindingDraft(
                    client_ref="G1",
                    kind=WorkspaceFindingKind.GOAL,
                    title="Accepted goal",
                    body="This entry advances the branch.",
                ),
            ),
        )
    )

    with pytest.raises(WorkspaceConflictError, match="base_revision is stale"):
        kernel.workspaces.write(
            WorkspaceWriteRequest(
                idempotency_key="workspace-write-stale-001",
                workspace_id=opened.workspace_id,
                branch_id=opened.branch_id,
                base_revision=opened.revision_id,
                findings=(
                    WorkspaceFindingDraft(
                        client_ref="G2",
                        kind=WorkspaceFindingKind.GOAL,
                        title="Must not commit",
                        body="This write uses a stale branch head.",
                    ),
                ),
            )
        )

    with sqlite3.connect(kernel.store.db_path) as connection:
        finding_count = connection.execute(
            "SELECT COUNT(*) FROM workspace_findings WHERE workspace_id = ?",
            (opened.workspace_id,),
        ).fetchone()[0]
        revision_count = connection.execute(
            "SELECT COUNT(*) FROM workspace_revisions WHERE workspace_id = ?",
            (opened.workspace_id,),
        ).fetchone()[0]
    assert finding_count == 2
    assert revision_count == 2
    current = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            view=WorkspaceQueryView.RESUME,
            revision_id=accepted.revision_id,
        )
    )
    assert current.revision_id == accepted.revision_id

    with pytest.raises(
        WorkspaceConflictError,
        match="query revision_id is stale",
    ):
        kernel.workspaces.query(
            WorkspaceQueryRequest(
                workspace_id=opened.workspace_id,
                branch_id=opened.branch_id,
                view=WorkspaceQueryView.RESUME,
                revision_id=opened.revision_id,
            )
        )


@pytest.mark.integration
def test_workspace_rejects_idempotency_rebinding_and_invalid_references(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    opened = _open(kernel, key="workspace-open-binding-001")

    with pytest.raises(WorkspaceIdempotencyError, match="different workspace request"):
        kernel.workspaces.open(
            WorkspaceOpenRequest(
                idempotency_key="workspace-open-binding-001",
                name="different",
                problem="This must not reuse the first workspace.",
            )
        )

    with pytest.raises(WorkspaceReferenceError, match="does not exist"):
        kernel.workspaces.write(
            WorkspaceWriteRequest(
                idempotency_key="workspace-write-missing-ref-001",
                workspace_id=opened.workspace_id,
                branch_id=opened.branch_id,
                base_revision=opened.revision_id,
                findings=(
                    WorkspaceFindingDraft(
                        client_ref="L1",
                        kind=WorkspaceFindingKind.CLAIM,
                        title="Dangling dependency",
                        body="This finding cites a missing card.",
                        dependency_refs=("card://00000000000000000000000000000000",),
                    ),
                ),
            )
        )

    with pytest.raises(WorkspaceReferenceError, match="contain a cycle"):
        kernel.workspaces.write(
            WorkspaceWriteRequest(
                idempotency_key="workspace-write-cycle-001",
                workspace_id=opened.workspace_id,
                branch_id=opened.branch_id,
                base_revision=opened.revision_id,
                findings=(
                    WorkspaceFindingDraft(
                        client_ref="L1",
                        kind=WorkspaceFindingKind.CLAIM,
                        title="First",
                        body="First cyclic claim.",
                        dependency_refs=("L2",),
                    ),
                    WorkspaceFindingDraft(
                        client_ref="L2",
                        kind=WorkspaceFindingKind.CLAIM,
                        title="Second",
                        body="Second cyclic claim.",
                        dependency_refs=("L1",),
                    ),
                ),
            )
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


def test_workspace_drafts_normalize_unambiguous_operational_aliases() -> None:
    goal = WorkspaceFindingDraft.model_validate(
        {
            "client_ref": "G1",
            "kind": "OPEN_GOAL",
            "title": "Finish the proof",
            "body": "This remains agent-authored and unverified.",
        }
    )
    attempt = WorkspaceAttemptDraft.model_validate(
        {
            "client_ref": "T1",
            "target_ref": "G1",
            "method": "direct",
            "outcome": "SUCCEEDED",
            "summary": "The operational attempt finished.",
        }
    )
    mark = WorkspaceMarkDraft.model_validate(
        {
            "client_ref": "M1",
            "target_ref": "G1",
            "state": "CLOSED",
            "summary": "The agent explicitly closed this work item.",
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


@pytest.mark.integration
def test_workspace_focus_clear_is_explicit_and_resumable(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    opened = _open(kernel, key="workspace-open-focus-clear-001")

    cleared = kernel.workspaces.write(
        WorkspaceWriteRequest(
            idempotency_key="workspace-write-focus-clear-001",
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            base_revision=opened.revision_id,
            focus=WorkspaceFocusDraft(clear=True),
        )
    )

    assert cleared.focus_updated is True
    resume = kernel.workspaces.query(
        WorkspaceQueryRequest(
            workspace_id=opened.workspace_id,
            branch_id=opened.branch_id,
            view=WorkspaceQueryView.RESUME,
        )
    )
    assert resume.resume is not None
    assert resume.resume.active_item is None
    assert resume.resume.pinned_items == ()


@pytest.mark.integration
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


@pytest.mark.integration
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


@pytest.mark.integration
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


@pytest.mark.integration
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


@pytest.mark.integration
def test_workspace_context_handles_a_deep_dependency_chain(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    opened = _open(kernel, key="workspace-open-deep-context-001")
    revision_id = opened.revision_id
    previous_card_id: str | None = None

    for batch_index in range(16):
        findings = []
        for item_index in range(64):
            client_ref = f"N{item_index}"
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
        written = kernel.workspaces.write(
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
    context = kernel.workspaces.query(
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


@pytest.mark.integration
def test_workspace_supersession_handles_a_deep_chain(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    opened = _open(kernel, key="workspace-open-deep-supersession-001")
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
        written = kernel.workspaces.write(
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
        written = kernel.workspaces.write(
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

    context = kernel.workspaces.query(
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


def test_workspace_mark_contracts_fail_closed() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot provide both reason and summary",
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


@pytest.mark.integration
def test_workspace_context_truncation_and_stale_roots_are_deterministic(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    opened = _open(kernel, key="workspace-open-context-budget-001")
    seeded = kernel.workspaces.write(
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
    marked = kernel.workspaces.write(
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

    result = kernel.workspaces.query(
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


@pytest.mark.integration
def test_workspace_invalid_marks_leave_no_partial_state(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path)
    opened = _open(kernel, key="workspace-open-invalid-mark-001")
    seeded = kernel.workspaces.write(
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
            kernel.workspaces.write(invalid)

    accepted = kernel.workspaces.write(
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
        kernel.workspaces.write(
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

    with sqlite3.connect(kernel.store.db_path) as connection:
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


@pytest.mark.integration
def test_workspace_invalidating_mark_requires_explicit_reactivation(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    opened = _open(kernel, key="workspace-open-explicit-reactivation-001")
    seeded = kernel.workspaces.write(
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
    retracted = kernel.workspaces.write(
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
        kernel.workspaces.write(
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

    unchanged = kernel.workspaces.query(
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


@pytest.mark.integration
def test_workspace_archiving_is_organizational_not_invalidation(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path)
    opened = _open(kernel, key="workspace-open-archive-001")
    seeded = kernel.workspaces.write(
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
    archived = kernel.workspaces.write(
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

    context = kernel.workspaces.query(
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
