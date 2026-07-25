# ADR 0003: Use SQLite acceptance with immutable search checkpoints

[Documentation home](../../index.md) · [Decision log](index.md)

- Status: Accepted
- Date: 2026-07-24

## Decision

Represent one strategy search with:

- a transactional SQLite idempotency binding and latest-snapshot row;
- an append-only, digest-linked lifecycle event chain;
- immutable archive pages, checkpoints, and terminal archives in the artifact
  store.

One idempotency key binds one exact request digest to one experiment URI.
Startup recovery pauses interrupted active work at the last committed
checkpoint. Invalid recovery rows are quarantined independently as `ERROR`.

The reference scheduler accepts one strategy worker and one active coordinator
per state directory. Multi-process leases and distributed queues are not part
of this decision.

## Rationale

SQLite provides the two properties the local runtime needs: atomic concurrent
request acceptance and durable indexed state. Immutable artifacts provide the
lineage and replay boundary. Keeping the latest snapshot mutable avoids
reconstructing every read from a long event stream, while the append-only events
retain audit history.

Opaque strategy state is safe to resume only when its checkpoint is rebound to
the accepted request, plugin snapshot, implementations, environment, effective
budget, accounting, and archive pages.

Plugin work may repeat after the last checkpoint if the process dies before
commit. This is acceptable because repeat execution cannot create a second
accepted experiment and uncommitted output is not durable lineage.

## Persistence and accounting boundary

An iteration stores its archive page and checkpoint before updating SQLite.
Wall time is sampled after checkpoint artifact creation and before the metadata
transaction. This includes artifact persistence in budget enforcement without
claiming resource measurements the local runtime does not observe.

## Alternatives considered

### In-memory threads only

Rejected because process loss would discard request identity, lineage, and
opaque strategy state.

### Pure event sourcing

Rejected for the local implementation because every inspect, wait, and control
operation would need to fold the entire event history. The validated latest
snapshot is a simpler read model.

### A queue service or PostgreSQL first

Deferred until multiple coordinators or remote workers are justified. Adding a
distributed system before a lease and failure model exists would weaken, not
strengthen, invocation identity.

### Exactly-once plugin execution

Rejected as an inaccurate promise. External work can repeat around a crash.
Jacobian guarantees one accepted invocation and one committed lineage, not that
an uncommitted child process ran only once.

## Consequences

- A state directory has one active coordinator.
- Concurrent retries are safe and observable as reuse events.
- Recovery can continue around one malformed row.
- Checkpoint and archive identity checks are trust-sensitive and require
  adversarial tests.
- A future distributed scheduler must preserve the same request, event,
  checkpoint, and checker-authority bindings.
