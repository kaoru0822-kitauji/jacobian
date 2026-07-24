# Milestone 3 specification: scalable search

[Documentation home](../../index.md)

- Status: Provisional implementation; outside v0.2 conformance
- Theme: Run typed search strategies through one durable experiment loop

## 1. Entry gate

Two domains must have validated the v0.2 enumeration, transformation, and
verification boundaries.

## 2. Orchestration contract

M3 generalizes the v0.2 enumeration runner into a strategy-neutral loop:

```text
propose candidates
    → validate candidates
    → evaluate and attack candidates
    → independently verify any counterexamples
    → record evidence, failures, and lineage
    → refine durable search state
    → nominate selected candidates for ordinary verification
    → checkpoint and continue
```

The engine owns lifecycle state, budgets, accounting, checkpoint publication,
and verification routing. A strategy owns only its versioned, mathematically
untrusted proposal and refinement state.

The loop preserves these distinctions:

- A proposed candidate is not a mathematical conclusion.
- An evaluator score is not a verification result.
- A proposed counterexample becomes verified feedback only after an authorized
  witness checker accepts it.
- Failure to find a counterexample remains `UNKNOWN`.
- A nominated candidate becomes verified only through the existing witness or
  certificate boundary.
- Exhausted strategy state is not exhaustive mathematical evidence unless an
  independently checked certificate binds the exact scope.

## 3. Plugin operations

M3 adds small optional capabilities rather than a mandatory search-framework
base class:

- A proposer consumes a claim, immutable search state, prior feedback, and a
  bounded request, then returns candidate proposals and updated opaque state.
- The existing evaluator and witness-oracle capabilities score and attack
  proposals without promoting their evidence.
- A refiner consumes prior state plus typed feedback. Verified
  counterexamples carry their verification records; heuristic observations
  remain explicitly unverified.
- A nomination policy selects candidates for the existing verification tools.
  It cannot authorize checkers or assign `VERIFIED`.

Plugin state is a versioned artifact bound to the plugin implementation,
strategy contract, claim, semantics, environment, and random state where
applicable. The kernel does not interpret algorithm-specific fields.

Exact enumeration, counterexample-guided refinement, constraint solving,
canonical generation, parameter sweeps, beam or tree search, evolutionary
search, and agent-driven loops may implement these operations. None is a
required kernel algorithm.

## 4. Tools and lifecycle

### `search.run`

Start or continue a bounded search using an installed strategy plugin. The
tool validates the claim and capability contracts, commits the request, and
returns a durable experiment handle before long-running work begins.

### `experiment.pause` and `experiment.resume`

Pause requests stop new work at a checkpoint boundary. Resume derives a new
lease from an immutable checkpoint rather than mutating prior evidence.
Checkpoints bind the request, claim, strategy and plugin identities, effective
policy, artifacts, environment, budget accounting, and random state.

Cancellation remains distinct from pause. A cancelled, timed-out, interrupted,
or failed experiment never acquires a mathematical conclusion from its
operational state.

## 5. Durable records

Every experiment preserves:

```text
exact request and effective policy
claim, semantics, plugin, strategy, and environment identities
candidate and parent lineage
proposal and refinement operations
evaluation envelopes and optional strategy metrics
proposed counterexamples and verified witness records
candidate nominations and resulting verification records
checkpoint state and random-state identity
scope, budget, timestamps, measured wall time, and operation accounting
typed failures, cancellation, timeout, and recovery events
```

Strategy metrics may be scalar, vector-valued, ordered, or absent. They cannot
replace hard validity constraints or assurance labels. A complete experiment
can be reconstructed without a host transcript.

Search acceptance is idempotent. Concurrent or transport-retried submissions
with the same idempotency key and request digest resolve to one experiment URI.
The key cannot be rebound to another request. Append-only lifecycle events bind
the accepted request, operation inputs and outputs, runtime identity, effective
policy, configured limits, observed runtimes, and retry lineage.

Plugin work after the last committed checkpoint may execute again after process
loss. That repeat is an attempt in the same durable invocation, not a second
accepted experiment. Only atomically committed archive pages, checkpoints, and
events become lineage.

Wall accounting includes plugin execution and artifact persistence through
creation of each immutable checkpoint. Jacobian samples the measurement
immediately after that artifact is created and before the following SQLite
metadata transaction; lifecycle events record the transaction's ordering.
Jacobian does not claim CPU, memory, network-byte, or filesystem-byte metering
that the local runtime does not observe.

## 6. Plugin packaging and conformance

Search plugins use sealed, versioned packages and immutable registry snapshots.
Package discovery validates capability contracts, implementation bytes,
runtime and build identity, and platform compatibility without importing
plugin code.

For the Python-first M3 runtime, a sealed package is an operator-installed
source package measured as a whole and bound to its manifest and registry
snapshot. Resolution remeasures those bytes before execution. M3 does not add
remote executable uploads, a bespoke package manager, or a container-image
pipeline.

A generic conformance kit covers success, declared failure, malformed output,
timeout, path and symlink attacks, changed implementation bytes, and
unsupported evidence promotion. A synthetic third plugin must pass without
kernel or MCP changes.

`jacobian.plugin_conformance` provides a standard runner over a sealed,
conformance-only plugin package in isolated test state, a search request, and
disposable package attack fixtures. Each suite execution uses a fresh
idempotency namespace. The runner drives declared search capabilities and the
conjecture workflow itself, performs registry attacks with fresh fixture state,
runs every generic check, and reports all failures together. Fault injection
belongs only in this disposable synthetic package; production plugins do not
expose conformance crash, malformed-output, or timeout controls.

## 7. Execution

Scale only as evidence requires:

1. Sequential reference implementation
2. Spawned local worker processes
3. Persistent local experiment queue
4. Distributed workers only after measured need

The first three stages use ordinary process boundaries, SQLite state, and the
existing artifact store. Distributed infrastructure is not an M3 requirement.
The reference scheduler currently accepts exactly one strategy worker; asking
for more fails validation rather than being silently clamped.

Local workers use explicit wall-clock and output limits, fixed seeds where the
backend supports them, and recorded environment identities. These are
operational and reproducibility controls, not a security sandbox. Jacobian does
not accept arbitrary executable uploads; operators install plugins and checkers
they consider safe to run locally.

For authority represented by Jacobian, effective worker policy is the
restrictive intersection of the plugin contract, operator policy, and
invocation request. A local worker inherits the network and filesystem boundary
of the operator process. Jacobian neither widens that boundary nor claims to
narrow it; operators requiring isolation must launch Jacobian under an
appropriate OS or container policy. Plugins and requests cannot widen budget,
artifact, capability, or checker authority.

## 8. Implemented scope and limits

The provisional reference implementation provides:

- proposer, evaluator, optional witness-oracle, refiner, and nomination flow;
- transactional idempotent request acceptance;
- immutable archive pages, checkpoints, and terminal archives;
- append-only lifecycle events;
- pause, resume, cancellation, timeout, and startup recovery;
- per-row quarantine for malformed recovery state;
- whole-package plugin snapshots and the synthetic conformance suite.

The scheduler accepts exactly one strategy worker. One active Jacobian process
must own a state directory; there is no lease protocol for multiple
coordinators. Plugin calls run in bounded child processes, but network and
filesystem access are inherited from the operator process. Accounting records
exact operation counts and measured wall time at the documented checkpoint
boundary; it does not claim CPU, memory, network-byte, or filesystem-byte
metering.

Operational detail and rationale are recorded in:

- [Durable search runtime](../../explanation/search-runtime.md)
- [Sealed plugin package ADR](../../explanation/adr/0002-sealed-plugin-packages.md)
- [Durable invocation ADR](../../explanation/adr/0003-durable-search-invocations.md)
- [Plugin conformance kit](../plugin-conformance.md)

## 9. Exit gate

Milestone 3 is complete when:

- a long strategy-neutral search can pause, resume, and reproduce its archive
  lineage and measured accounting at the documented persistence boundary;
- independently verified counterexamples influence subsequent refinement;
- nominated candidates cross the existing checker boundary;
- concurrent or retried requests create one durable invocation;
- process loss can be reconstructed without chat state and resumed without
  losing or duplicating lineage;
- one malformed persisted invocation is quarantined without preventing
  unrelated invocations from recovering;
- a sealed synthetic plugin passes generic conformance without kernel or MCP
  changes;
- worker timeout and output-limit tests fail safely;
- workers cannot widen execution policy or checker authority;
- distributed execution, if present, cannot forge checker authorization.
