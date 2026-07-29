# ADR 0005: Keep epistemic workspaces separate from capability assurance

[Documentation home](../../index.md) · [Decision log](index.md)

- Status: Accepted for the pre-stable capability workbench
- Date: 2026-07-25
- Amended: 2026-07-26 to add paper-like lifecycle marks and derived staleness

## Decision

Implement durable agent working state as an independent `WorkspaceService`, not
as a mathematical capability adapter. Project it through three direct MCP
tools alongside the two capability tools:

- `workspace.open`
- `workspace.write`
- `workspace.query`

Workspace mutations return operational revision handles. They do not return
heuristic, computed, or verified mathematical assurance. Every stored finding,
attempt, and lifecycle mark is explicitly agent-authored and `UNVERIFIED`.

Represent one workspace branch with:

- an immutable, content-addressed revision artifact for every accepted batch;
- a stable workspace, branch, revision, and item identity;
- append-only lifecycle marks over immutable finding cards;
- a transactional SQLite branch head and query index;
- an idempotency binding for each accepted mutation;
- optimistic writes bound to the exact current `base_revision`.

The initial implementation creates one pinned `main` branch and exactly one
canonical problem card; only `workspace.open` may create that card. An agent
may explicitly mark a non-problem card `ACTIVE`, `CLOSED`, `RETRACTED`,
`SUPERSEDED`, or `ARCHIVED`. `RETRACTED` and `SUPERSEDED` are invalidation
roots. Clearing either warning requires an explicit `ACTIVE` mark before a
later `CLOSED` or `ARCHIVED` mark. Query-time staleness follows only recorded
dependency and assumption links. Fork, cherry-pick, search, and evidence
attachment require later contracts and do not acquire implicit behavior from
this decision.

## Rationale

`CapabilityService` describes mathematical operations whose results have
heuristic, computed, or verified assurance. Successfully recording a note,
goal, or attempt is an operational fact, not a mathematical computation.
Forcing workspace writes through `CapabilityResult` would make a state change
look like mathematical evidence and would record recursive capability episodes
for the workspace itself.

The direct tools also make frequent checkpoint and resume operations visible to
an agent without requiring capability discovery for operational state changes.
Three tools keep the MCP surface compact while separating mathematical
instruments from the state used to coordinate them.

The persistence design follows the same local pattern as durable search:
SQLite provides atomic acceptance and indexed current state, while immutable
artifacts preserve history and lineage. Pure event replay would make every
resume query fold the full history. Mutable note rows alone would lose the
accepted revision boundary.

## Trust boundary

Workspace storage validates structure, identity, scope, and explicit
references. It does not decide whether:

- a claim is true;
- an attempt succeeded mathematically;
- a dependency is semantically complete;
- two findings are equivalent;
- a formal proof corresponds to an informal card.

Caller-controlled input cannot set a finding or attempt to `VERIFIED`.
It also cannot write a derived `STALE` value. `CLOSED` means an agent explicitly
closed a work item; it does not mean the goal was proved. A completed attempt
does not close its target automatically. Supersession records a replacement
pointer but does not establish equivalence or reconnect old dependents.
Retrieval, focus, pinning, lifecycle marks, and future publication between
branches must retain the original assurance. A later evidence-attachment
contract must validate an authorized local verification record and its exact
formal bindings rather than trusting a caller-supplied evidence label.

## Consequences

- The MCP server advertises five tools rather than two. There are no alternate
  tool profiles; individual mathematical operations remain behind capability
  IDs.
- Workspace revisions and capability research episodes remain distinct data
  types but may be linked in later revisions through artifact handles.
- Retry-safe clients must provide an idempotency key and current base revision
  for every mutation.
- `RESUME` and `FRONTIER` treat only explicitly `ACTIVE` goals as open.
  Active-but-stale goals remain visible with their invalidation roots.
- `CONTEXT` returns a bounded deterministic closure over explicit dependency and
  assumption links; truncation is reported rather than hidden. `STALE` lists
  cards downstream of current invalidation roots.
- Queries read their branch head, cards, marks, attempts, scratch, and focus
  from one SQLite snapshot. Append order, not caller-controlled wall-clock
  timestamps, determines the current mark and recent-item order.
- A stale write fails before indexed workspace state changes. An immutable
  artifact created during a losing cross-process race may remain unreferenced,
  but it is never accepted as branch history.
- Workspace entries are tenant-isolated through the existing per-subject
  runtime root.
