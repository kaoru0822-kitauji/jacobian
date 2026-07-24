# Milestone 3 specification: scalable search

- Status: Provisional
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
scope, budget, timestamps, and resource accounting
typed failures, cancellation, timeout, and recovery events
```

Strategy metrics may be scalar, vector-valued, ordered, or absent. They cannot
replace hard validity constraints or assurance labels. A complete experiment
can be reconstructed without a host transcript.

Worker invocations are idempotent. Concurrent or transport-retried requests
resolve to one accepted invocation, and append-only lifecycle events bind the
exact inputs, outputs, runtime identity, effective policy, resource use, and
retry lineage.

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

## 7. Execution

Scale only as evidence requires:

1. Sequential reference implementation
2. Spawned local worker processes
3. Persistent local experiment queue
4. Distributed workers only after measured need

The first three stages use ordinary process boundaries, SQLite state, and the
existing artifact store. Distributed infrastructure is not an M3 requirement.

Local workers use explicit wall-clock and output limits, fixed seeds where the
backend supports them, and recorded environment identities. These are
operational and reproducibility controls, not a security sandbox. Jacobian does
not accept arbitrary executable uploads; operators install plugins and checkers
they consider safe to run locally.

Effective worker authority is the restrictive intersection of the plugin
contract, operator policy, and invocation request. No layer may widen resource,
network, filesystem, artifact, or checker authority.

## 8. Exit gate

Milestone 3 is complete when:

- a long strategy-neutral search can pause, resume, and reproduce its archive
  lineage and exact accounting;
- independently verified counterexamples influence subsequent refinement;
- nominated candidates cross the existing checker boundary;
- concurrent or retried requests create one durable invocation;
- process loss can be reconstructed without chat state and resumed without
  losing or duplicating lineage;
- a sealed synthetic plugin passes generic conformance without kernel or MCP
  changes;
- worker timeout, output-limit, and resource-exhaustion tests fail safely;
- workers cannot widen execution policy or checker authority;
- distributed execution, if present, cannot forge checker authorization.
