"""Versioned contracts for the agent-authored epistemic workspace."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    model_validator,
)

from jacobian.contracts.common import ArtifactUri, Sha256Digest
from jacobian.contracts.results import ContractModel

WorkspaceId = Annotated[
    str,
    StringConstraints(
        pattern=r"^workspace://[0-9a-f]{32}$",
        strict=True,
    ),
]
WorkspaceBranchId = Annotated[
    str,
    StringConstraints(
        pattern=r"^branch://[0-9a-f]{32}$",
        strict=True,
    ),
]
WorkspaceRevisionId = Annotated[
    str,
    StringConstraints(
        pattern=r"^revision://[0-9a-f]{32}$",
        strict=True,
    ),
]
WorkspaceItemId = Annotated[
    str,
    StringConstraints(
        pattern=r"^(?:card|scratch|attempt|mark)://[0-9a-f]{32}$",
        strict=True,
    ),
]
WorkspaceCardId = Annotated[
    str,
    StringConstraints(
        pattern=r"^card://[0-9a-f]{32}$",
        strict=True,
    ),
]
WorkspaceClientRef = Annotated[
    str,
    StringConstraints(
        pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$",
        strict=True,
    ),
]
WorkspaceReference = Annotated[
    str,
    StringConstraints(
        pattern=(
            r"^(?:[A-Za-z][A-Za-z0-9_.-]{0,63}"
            r"|card://[0-9a-f]{32})$"
        ),
        strict=True,
    ),
]
WorkspaceIdempotencyKey = Annotated[
    str,
    StringConstraints(
        pattern=r"^[A-Za-z0-9._:-]{8,128}$",
        strict=True,
    ),
]
WorkspaceTag = Annotated[
    str,
    StringConstraints(
        pattern=r"^[^\s]{1,64}$",
        strict=True,
    ),
]


class WorkspaceFindingKind(StrEnum):
    PROBLEM = "PROBLEM"
    ASSUMPTION = "ASSUMPTION"
    DEFINITION = "DEFINITION"
    GOAL = "GOAL"
    FINDING = "FINDING"
    CLAIM = "CLAIM"
    EXAMPLE = "EXAMPLE"
    COUNTEREXAMPLE = "COUNTEREXAMPLE"
    STRATEGY = "STRATEGY"
    OBSTACLE = "OBSTACLE"
    OPEN_QUESTION = "OPEN_QUESTION"


class WorkspaceAttemptOutcome(StrEnum):
    PROPOSED = "PROPOSED"
    PROMISING = "PROMISING"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class WorkspaceCardState(StrEnum):
    """Agent-recorded paper-like lifecycle state, never mathematical assurance."""

    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    RETRACTED = "RETRACTED"
    SUPERSEDED = "SUPERSEDED"
    ARCHIVED = "ARCHIVED"


class WorkspaceRevisionOperation(StrEnum):
    OPEN = "OPEN"
    WRITE = "WRITE"


class WorkspaceQueryView(StrEnum):
    RESUME = "RESUME"
    FRONTIER = "FRONTIER"
    ATTEMPTS = "ATTEMPTS"
    CONTEXT = "CONTEXT"
    STALE = "STALE"


class WorkspaceScratchDraft(ContractModel):
    """One agent-authored, unverified scratch entry."""

    client_ref: WorkspaceClientRef = Field(
        description=(
            "A local identifier unique within this write, such as S1. Other entries "
            "in the same write may cite it before the service assigns a scratch:// ID."
        )
    )
    body: str = Field(
        min_length=1,
        max_length=8192,
        description=(
            "Unverified scratch text. Assurance is assigned by the service; do not "
            "send verification or assertion fields."
        ),
    )
    tags: tuple[WorkspaceTag, ...] = Field(
        default=(),
        max_length=16,
        description="Optional unique, whitespace-free tags.",
    )

    @model_validator(mode="after")
    def require_unique_tags(self) -> Self:
        if len(set(self.tags)) != len(self.tags):
            raise ValueError("scratch tags must be unique")
        return self


class WorkspaceFindingDraft(ContractModel):
    """One typed, agent-authored, unverified epistemic card."""

    client_ref: WorkspaceClientRef = Field(
        description=(
            "A local identifier unique within this write, such as G1 or claim-341. "
            "Use it from target_ref, dependency_refs, assumption_refs, or focus fields "
            "in the same batch."
        )
    )
    kind: WorkspaceFindingKind = Field(
        description=(
            "Card type. Use GOAL for unfinished work and CLAIM or COUNTEREXAMPLE for "
            "a result. Use FINDING for a generic observation. PROBLEM is reserved for "
            "the canonical card created by workspace.open and is rejected by "
            "workspace.write."
        )
    )
    title: str = Field(
        min_length=1,
        max_length=256,
        description="Short human-readable card title.",
    )
    body: str = Field(
        min_length=1,
        max_length=16_384,
        description=(
            "Agent-authored content stored as AGENT_RECORDED and UNVERIFIED; do not "
            "send verification or assertion fields."
        ),
    )
    dependency_refs: tuple[WorkspaceReference, ...] = Field(
        default=(),
        max_length=64,
        description=(
            "Unique card:// IDs or finding client_ref values from this same write "
            "whose results this card depends on."
        ),
    )
    assumption_refs: tuple[WorkspaceReference, ...] = Field(
        default=(),
        max_length=64,
        description=(
            "Unique card:// IDs or finding client_ref values from this same write "
            "that this card assumes."
        ),
    )
    tags: tuple[WorkspaceTag, ...] = Field(
        default=(),
        max_length=16,
        description="Optional unique, whitespace-free tags.",
    )

    @model_validator(mode="after")
    def require_unique_references(self) -> Self:
        if len(set(self.dependency_refs)) != len(self.dependency_refs):
            raise ValueError("finding dependency references must be unique")
        if len(set(self.assumption_refs)) != len(self.assumption_refs):
            raise ValueError("finding assumption references must be unique")
        if set(self.dependency_refs) & set(self.assumption_refs):
            raise ValueError(
                "a finding reference cannot be both a dependency and an assumption"
            )
        if len(set(self.tags)) != len(self.tags):
            raise ValueError("finding tags must be unique")
        return self


class WorkspaceAttemptDraft(ContractModel):
    """One operational attempt report; completion is not mathematical verification."""

    client_ref: WorkspaceClientRef = Field(
        description=(
            "A local identifier unique within this write, such as T1. The service "
            "returns its assigned attempt:// ID in id_map."
        )
    )
    target_ref: WorkspaceReference = Field(
        description=(
            "The target card:// ID or a finding client_ref introduced in this same "
            "write. Use target_ref, not target_card_id."
        )
    )
    method: str = Field(
        min_length=1,
        max_length=128,
        description="Short name or description of the attempted method.",
    )
    outcome: WorkspaceAttemptOutcome = Field(
        description=(
            "Operational status: PROPOSED, PROMISING, BLOCKED, FAILED, or COMPLETED. "
            "A finished attempt never means VERIFIED."
        )
    )
    summary: str = Field(
        min_length=1,
        max_length=4096,
        description=(
            "Agent-authored outcome summary stored as AGENT_RECORDED and UNVERIFIED; "
            "do not send verification or assertion fields."
        ),
    )
    artifact_uris: tuple[ArtifactUri, ...] = Field(
        default=(),
        max_length=32,
        description="Optional unique artifact:// attachments.",
    )
    tags: tuple[WorkspaceTag, ...] = Field(
        default=(),
        max_length=16,
        description="Optional unique, whitespace-free tags.",
    )

    @model_validator(mode="after")
    def require_unique_attachments(self) -> Self:
        if len(set(self.artifact_uris)) != len(self.artifact_uris):
            raise ValueError("attempt artifact URIs must be unique")
        if len(set(self.tags)) != len(self.tags):
            raise ValueError("attempt tags must be unique")
        return self


class WorkspaceFocusDraft(ContractModel):
    """An explicit focus update or clear operation."""

    active_ref: WorkspaceReference | None = Field(
        default=None,
        description=(
            "Set the active card using a card:// ID or a finding client_ref from this "
            "same write. Focus references identify finding cards only, never an "
            "attempt or scratch entry."
        ),
    )
    pinned_refs: tuple[WorkspaceReference, ...] = Field(
        default=(),
        max_length=32,
        description=(
            "Replace pinned cards with these unique card:// IDs or finding client_ref "
            "values from this same write. A pin is always a finding card, never an "
            "attempt or scratch entry."
        ),
    )
    clear: StrictBool = Field(
        default=False,
        description=(
            "Set clear=true to remove the active card and all pins. Do not combine it "
            "with active_ref or pinned_refs; an empty focus object is invalid."
        ),
    )

    @model_validator(mode="after")
    def require_explicit_update_and_unique_pins(self) -> Self:
        if len(set(self.pinned_refs)) != len(self.pinned_refs):
            raise ValueError("pinned references must be unique")
        if self.clear and (self.active_ref is not None or self.pinned_refs):
            raise ValueError(
                "focus clear cannot be combined with active_ref or pinned_refs"
            )
        if self.active_ref is None and not self.pinned_refs and not self.clear:
            raise ValueError(
                "focus update requires active_ref, pinned_refs, or clear=true"
            )
        return self


class WorkspaceMarkDraft(ContractModel):
    """One explicit margin mark over a card; it does not alter mathematical assurance."""

    client_ref: WorkspaceClientRef = Field(
        description=(
            "A local identifier unique within this write, such as M1. The service "
            "returns its assigned mark:// ID in id_map."
        )
    )
    target_ref: WorkspaceReference = Field(
        description=(
            "The card:// ID to mark or a finding client_ref introduced in this same "
            "write."
        )
    )
    state: WorkspaceCardState = Field(
        description=(
            "Agent-recorded lifecycle state. CLOSED applies only to GOAL or "
            "OPEN_QUESTION and means work was explicitly closed, not proved. "
            "RETRACTED and SUPERSEDED invalidate dependent workspace cards without "
            "assigning a mathematical conclusion. Either invalidating state requires "
            "an explicit ACTIVE restoration before CLOSED or ARCHIVED. The canonical "
            "PROBLEM cannot be marked."
        )
    )
    reason: str = Field(
        min_length=1,
        max_length=2048,
        description=(
            "Why the margin mark was made. Stored as AGENT_RECORDED and UNVERIFIED."
        ),
    )
    superseded_by_ref: WorkspaceReference | None = Field(
        default=None,
        description=(
            "Replacement card:// ID or same-write finding client_ref. Required only "
            "when state is SUPERSEDED."
        ),
    )

    @model_validator(mode="after")
    def bind_replacement_to_superseded_state(self) -> Self:
        if (
            self.state is WorkspaceCardState.SUPERSEDED
            and self.superseded_by_ref is None
        ):
            raise ValueError("SUPERSEDED marks require superseded_by_ref")
        if (
            self.state is not WorkspaceCardState.SUPERSEDED
            and self.superseded_by_ref is not None
        ):
            raise ValueError("only SUPERSEDED marks may carry superseded_by_ref")
        return self


class WorkspaceOpenRequest(ContractModel):
    request_version: Literal["1"] = "1"
    idempotency_key: WorkspaceIdempotencyKey
    name: str = Field(min_length=1, max_length=128)
    problem: str = Field(min_length=1, max_length=16_384)
    tags: tuple[WorkspaceTag, ...] = Field(default=(), max_length=16)

    @model_validator(mode="after")
    def require_unique_tags(self) -> Self:
        if len(set(self.tags)) != len(self.tags):
            raise ValueError("workspace tags must be unique")
        return self


class WorkspaceWriteRequest(ContractModel):
    request_version: Literal["1"] = "1"
    idempotency_key: WorkspaceIdempotencyKey
    workspace_id: WorkspaceId
    branch_id: WorkspaceBranchId
    base_revision: WorkspaceRevisionId
    scratch: tuple[WorkspaceScratchDraft, ...] = Field(
        default=(),
        max_length=64,
        description="Scratch entries to append.",
    )
    findings: tuple[WorkspaceFindingDraft, ...] = Field(
        default=(),
        max_length=64,
        description="Typed epistemic cards to append.",
    )
    attempts: tuple[WorkspaceAttemptDraft, ...] = Field(
        default=(),
        max_length=64,
        description="Operational attempt reports to append.",
    )
    marks: tuple[WorkspaceMarkDraft, ...] = Field(
        default=(),
        max_length=64,
        description=(
            "Explicit lifecycle marks to append. Marks never promote mathematical "
            "assurance."
        ),
    )
    focus: WorkspaceFocusDraft | None = Field(
        default=None,
        description=(
            "Optional explicit focus replacement. Use active_ref/pinned_refs to set "
            "focus or clear=true to clear it; omit focus to leave it unchanged."
        ),
    )

    @model_validator(mode="after")
    def require_one_mutation_and_unique_refs(self) -> Self:
        if not (
            self.scratch or self.findings or self.attempts or self.marks or self.focus
        ):
            raise ValueError("workspace write requires at least one mutation")
        if any(
            finding.kind is WorkspaceFindingKind.PROBLEM for finding in self.findings
        ):
            raise ValueError(
                "only workspace.open may create the canonical PROBLEM card"
            )
        refs = [
            entry.client_ref
            for entries in (self.scratch, self.findings, self.attempts, self.marks)
            for entry in entries
        ]
        if len(set(refs)) != len(refs):
            raise ValueError("workspace write client references must be unique")
        mark_targets = [mark.target_ref for mark in self.marks]
        if len(set(mark_targets)) != len(mark_targets):
            raise ValueError(
                "a workspace write may append at most one mark per target card"
            )
        if self.focus is not None:
            focus_refs = {
                reference
                for reference in (
                    self.focus.active_ref,
                    *self.focus.pinned_refs,
                )
                if reference is not None
            }
            nonfinding_refs = (
                {entry.client_ref for entry in self.scratch}
                | {entry.client_ref for entry in self.attempts}
                | {entry.client_ref for entry in self.marks}
            )
            if focus_refs & nonfinding_refs:
                raise ValueError(
                    "focus references must identify finding cards, not scratch or "
                    "attempt entries"
                )
        return self


class WorkspaceQueryRequest(ContractModel):
    request_version: Literal["1"] = "1"
    workspace_id: WorkspaceId
    branch_id: WorkspaceBranchId
    revision_id: WorkspaceRevisionId | None = Field(
        default=None,
        description=(
            "Optional expected branch head. The query fails closed if the current "
            "head differs; omit it to read the latest head."
        ),
    )
    view: WorkspaceQueryView
    target_card_id: WorkspaceCardId | None = None
    limit: StrictInt = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def bind_target_to_targeted_views(self) -> Self:
        if self.view is WorkspaceQueryView.CONTEXT and self.target_card_id is None:
            raise ValueError("target_card_id is required for the CONTEXT view")
        if self.target_card_id is not None and self.view not in (
            WorkspaceQueryView.ATTEMPTS,
            WorkspaceQueryView.CONTEXT,
        ):
            raise ValueError(
                "target_card_id is only valid for ATTEMPTS or CONTEXT views"
            )
        return self


class WorkspaceScratchEntry(ContractModel):
    scratch_id: WorkspaceItemId
    body: str
    tags: tuple[str, ...] = ()
    created_revision: WorkspaceRevisionId
    created_at: datetime


class WorkspaceFinding(ContractModel):
    card_id: WorkspaceCardId
    kind: WorkspaceFindingKind
    title: str
    body: str
    dependency_ids: tuple[WorkspaceCardId, ...] = ()
    assumption_ids: tuple[WorkspaceCardId, ...] = ()
    tags: tuple[str, ...] = ()
    assertion: Literal["AGENT_RECORDED"] = "AGENT_RECORDED"
    verification: Literal["UNVERIFIED"] = "UNVERIFIED"
    created_revision: WorkspaceRevisionId
    created_at: datetime


class WorkspaceAttempt(ContractModel):
    attempt_id: WorkspaceItemId
    target_card_id: WorkspaceCardId
    method: str
    outcome: WorkspaceAttemptOutcome
    summary: str
    artifact_uris: tuple[ArtifactUri, ...] = ()
    tags: tuple[str, ...] = ()
    assertion: Literal["AGENT_RECORDED"] = "AGENT_RECORDED"
    verification: Literal["UNVERIFIED"] = "UNVERIFIED"
    created_revision: WorkspaceRevisionId
    created_at: datetime


class WorkspaceMark(ContractModel):
    mark_id: WorkspaceItemId
    target_card_id: WorkspaceCardId
    state: WorkspaceCardState
    reason: str
    superseded_by_id: WorkspaceCardId | None = None
    assertion: Literal["AGENT_RECORDED"] = "AGENT_RECORDED"
    verification: Literal["UNVERIFIED"] = "UNVERIFIED"
    created_revision: WorkspaceRevisionId
    created_at: datetime


class WorkspaceFocus(ContractModel):
    active_item_id: WorkspaceCardId | None = None
    pinned_item_ids: tuple[WorkspaceCardId, ...] = ()
    updated_revision: WorkspaceRevisionId


class WorkspaceRevision(ContractModel):
    revision_version: Literal["1"] = "1"
    revision_id: WorkspaceRevisionId
    workspace_id: WorkspaceId
    branch_id: WorkspaceBranchId
    parent_revision: WorkspaceRevisionId | None = None
    operation: WorkspaceRevisionOperation
    request_digest: Sha256Digest
    scratch: tuple[WorkspaceScratchEntry, ...] = ()
    findings: tuple[WorkspaceFinding, ...] = ()
    attempts: tuple[WorkspaceAttempt, ...] = ()
    marks: tuple[WorkspaceMark, ...] = ()
    focus: WorkspaceFocus | None = None
    created_at: datetime


class WorkspaceOpenResult(ContractModel):
    result_version: Literal["1"] = "1"
    workspace_id: WorkspaceId
    branch_id: WorkspaceBranchId
    revision_id: WorkspaceRevisionId
    revision_artifact_uri: ArtifactUri
    problem_card_id: WorkspaceCardId


class WorkspaceWriteResult(ContractModel):
    result_version: Literal["1"] = "1"
    workspace_id: WorkspaceId
    branch_id: WorkspaceBranchId
    revision_id: WorkspaceRevisionId
    revision_artifact_uri: ArtifactUri
    id_map: dict[WorkspaceClientRef, WorkspaceItemId]
    scratch_written: StrictInt = Field(ge=0)
    findings_written: StrictInt = Field(ge=0)
    attempts_written: StrictInt = Field(ge=0)
    marks_written: StrictInt = Field(default=0, ge=0)
    focus_updated: bool
    unverified_finding_ids: tuple[WorkspaceCardId, ...] = ()
    unresolved_dependency_ids: tuple[WorkspaceCardId, ...] = ()
    assurance_notice: Literal[
        "Workspace findings, attempts, search counts, TIMEOUT, and UNKNOWN remain "
        "UNVERIFIED and cannot establish an exact mathematical conclusion."
    ] = (
        "Workspace findings, attempts, search counts, TIMEOUT, and UNKNOWN remain "
        "UNVERIFIED and cannot establish an exact mathematical conclusion."
    )


class WorkspaceItemSummary(ContractModel):
    card_id: WorkspaceCardId
    kind: WorkspaceFindingKind
    title: str
    body_excerpt: str
    dependency_ids: tuple[WorkspaceCardId, ...] = ()
    assumption_ids: tuple[WorkspaceCardId, ...] = ()
    tags: tuple[str, ...] = ()
    state: WorkspaceCardState = WorkspaceCardState.ACTIVE
    state_reason: str | None = None
    state_mark_id: WorkspaceItemId | None = None
    superseded_by_id: WorkspaceCardId | None = None
    state_revision: WorkspaceRevisionId | None = None
    state_revision_artifact_uri: ArtifactUri | None = None
    stale: StrictBool = False
    stale_due_to_ids: tuple[WorkspaceCardId, ...] = ()
    verification: Literal["UNVERIFIED"] = "UNVERIFIED"
    created_revision: WorkspaceRevisionId
    created_revision_artifact_uri: ArtifactUri


class WorkspaceScratchSummary(ContractModel):
    scratch_id: WorkspaceItemId
    body_excerpt: str
    tags: tuple[str, ...] = ()
    created_revision: WorkspaceRevisionId
    created_revision_artifact_uri: ArtifactUri


class WorkspaceAttemptSummary(ContractModel):
    attempt_id: WorkspaceItemId
    target_card_id: WorkspaceCardId
    method: str
    outcome: WorkspaceAttemptOutcome
    summary_excerpt: str
    artifact_uris: tuple[ArtifactUri, ...] = ()
    verification: Literal["UNVERIFIED"] = "UNVERIFIED"
    created_revision: WorkspaceRevisionId
    created_revision_artifact_uri: ArtifactUri


class WorkspaceResumeView(ContractModel):
    name: str
    problem: WorkspaceItemSummary
    active_item: WorkspaceItemSummary | None = None
    pinned_items: tuple[WorkspaceItemSummary, ...] = ()
    open_goals: tuple[WorkspaceItemSummary, ...] = ()
    stale_items: tuple[WorkspaceItemSummary, ...] = ()
    recent_findings: tuple[WorkspaceItemSummary, ...] = ()
    recent_attempts: tuple[WorkspaceAttemptSummary, ...] = ()
    recent_scratch: tuple[WorkspaceScratchSummary, ...] = ()


class WorkspaceFrontierItem(ContractModel):
    goal: WorkspaceItemSummary
    attempt_count: StrictInt = Field(ge=0)
    last_attempt: WorkspaceAttemptSummary | None = None


class WorkspaceContextView(ContractModel):
    target: WorkspaceItemSummary
    dependencies: tuple[WorkspaceItemSummary, ...] = ()
    recent_attempts: tuple[WorkspaceAttemptSummary, ...] = ()
    total_dependency_count: StrictInt = Field(ge=0)
    truncated: StrictBool = False


class WorkspaceQueryResult(ContractModel):
    result_version: Literal["1"] = "1"
    workspace_id: WorkspaceId
    branch_id: WorkspaceBranchId
    revision_id: WorkspaceRevisionId
    revision_artifact_uri: ArtifactUri
    view: WorkspaceQueryView
    warning: Literal[
        "Workspace content is agent-authored and unverified; retrieval does not "
        "promote mathematical assurance. Derived staleness follows explicit recorded "
        "links only."
    ] = (
        "Workspace content is agent-authored and unverified; retrieval does not "
        "promote mathematical assurance. Derived staleness follows explicit recorded "
        "links only."
    )
    resume: WorkspaceResumeView | None = None
    frontier: tuple[WorkspaceFrontierItem, ...] = ()
    attempts: tuple[WorkspaceAttemptSummary, ...] = ()
    context: WorkspaceContextView | None = None
    stale_items: tuple[WorkspaceItemSummary, ...] = ()

    @model_validator(mode="after")
    def require_selected_view_payload(self) -> Self:
        if self.view is WorkspaceQueryView.RESUME and self.resume is None:
            raise ValueError("RESUME query result requires a resume payload")
        if self.view is not WorkspaceQueryView.RESUME and self.resume is not None:
            raise ValueError("only RESUME query results may carry a resume payload")
        if self.view is not WorkspaceQueryView.FRONTIER and self.frontier:
            raise ValueError("only FRONTIER query results may carry frontier items")
        if self.view is not WorkspaceQueryView.ATTEMPTS and self.attempts:
            raise ValueError("only ATTEMPTS query results may carry attempts")
        if self.view is WorkspaceQueryView.CONTEXT and self.context is None:
            raise ValueError("CONTEXT query result requires a context payload")
        if self.view is not WorkspaceQueryView.CONTEXT and self.context is not None:
            raise ValueError("only CONTEXT query results may carry a context payload")
        if self.view is not WorkspaceQueryView.STALE and self.stale_items:
            raise ValueError("only STALE query results may carry stale items")
        return self
