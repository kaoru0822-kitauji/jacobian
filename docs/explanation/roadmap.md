# Roadmap

[Documentation home](../index.md)

- Status: Active planning document
- Scheduling policy: Milestone gates are not promised dates or package versions
- Related records: [Architecture](architecture.md) and
  [architecture decision log](adr/index.md)

## Release and milestone policy

Each milestone is gated by evidence, not by a calendar date. Later milestone
work does not begin until the preceding trust and compatibility gates pass.

v0.2 is the current and only supported pre-stable alpha contract. M3 through
M5 are capability milestones, not promised package versions or compatibility
releases. Their scope and APIs may change. v1.0 remains a stability target
rather than the next scheduled release.

## Current product track — Capability workbench

Status: initial implementation in the repository; pre-stable and outside the
v0.2 conformance contract.

### Objective

Make Jacobian useful before verification by giving agents one compact,
extensible API for mathematical tools and local research memory, while keeping
checker-backed assurance available when a result must be promoted.

### Deliverables

- Model-facing `capability.describe` and `capability.invoke` MCP tools
- Adapter registration without kernel or MCP edits
- Explicit `EXPLORE` and `VERIFY` lanes
- Heuristic, computed, and verified assurance labels
- Local searchable research episodes with immutable provenance
- Streamable HTTP and SSE transports
- Bearer-token authentication and subject-bound tenant state
- Container and reverse-proxy deployment guidance
- Paired control/treatment agent benchmark with transcript-level metrics
- At least one external Alloy, SAT/SMT, or CAS adapter exercise

### Exit gate

A held-out, repeated A/B evaluation shows that the capability condition
improves correctness or resource use over the same model without Jacobian,
without increasing false certification. A synthetic external adapter appears
through MCP without editing the kernel or MCP server. Authenticated tenant
tests demonstrate that tools and resources cannot read another tenant's
artifacts or research episodes.

## v0.2 — Bounded discovery

Status: implemented in `0.2.0a0`.

### Objective

Provide one fail-closed kernel that can verify supplied candidates, search
bounded candidate classes, and independently verify representation changes.

### Deliverables

- Versioned claim, candidate, witness, certificate, and result schemas
- Canonical artifact encoding and domain-separated hashing
- Digest-keyed local artifact store and SQLite registry metadata
- Immutable verification-record artifacts
- Operator-managed checker registry
- Seven generic verification tools
- A generic plugin capability API
- At least two structurally different reference plugins and replay checkers
- CLI and thin MCP adapter
- Adversarial fail-closed verification suite
- Bounded enumeration experiments
- Search-safe canonicalization and symmetry rejection
- Transformation proposal and independent transformation verification
- Exact polyhedral projection and separation
- Persistent experiment handles and cancellation
- Verification and bounded-discovery workflows exercised in both reference
  plugins

### Exit gate

Both reference plugins replay exact evidence, reject deliberately corrupted
evidence, and complete bounded searches with auditable scope. At least one
representation transformation and exact separator are independently verified.
Every normative v0.2 conformance case passes in a clean installed environment,
including enumeration-limit, transformation-direction, and canonicalization
attacks.

The alpha exact-polytope scope is finite V-representation membership,
coordinate projection, and strict separation. Broader H/V conversion and
facet tooling remain optional backend work rather than release-gate claims.

## M3 — Scalable search

Implementation status: a provisional local single-worker implementation is in
the repository. It is not part of the v0.2 release contract. Distributed
execution and multi-process leases remain conditional on measured need.

### Entry gate

Bounded enumeration and transformation APIs have proved useful in two different
domains.

### Objective

Run large heuristic, exact, and agent-driven searches through one durable
orchestration loop while retaining lineage, failure evidence, and
exact-verification boundaries.

### Deliverables

- Typed proposer, evaluator, counterexample, refinement, and candidate
  nomination interfaces
- Strategy-neutral search state, checkpoints, lineage, and failure archives
- Verified-counterexample feedback through the existing witness boundary
- Candidate nomination that routes every mathematical promotion through the
  existing verification boundary
- Exact budget, scope, and runtime identity, with measured wall time and
  durable operation accounting
- Resumable, cancellable, and recoverable experiments
- Bounded local child-process execution; multi-process scheduling only after a
  lease model and measured need
- Resource-bounded local execution for operator-approved generated candidate
  code, without claiming a security sandbox
- Sealed, versioned plugin packages and immutable registry snapshots binding
  capability contracts, implementation bytes, runtime and build identity, and
  platform compatibility; discovery does not import plugin code
- A generic plugin conformance kit covering success, declared failure,
  malformed output, timeout, path and symlink attacks, changed implementation
  bytes, and unsupported evidence promotion
- A no-core-change extension gate exercised by a synthetic third plugin
- Idempotent, reconstructable search invocations with append-only lifecycle
  events binding the exact request, plugin and runtime identity, effective
  policy, inputs, outputs, configured limits, observed runtimes, and retry
  lineage

For authority represented by Jacobian, the effective worker policy is the
restrictive intersection of the plugin contract, operator policy, and
invocation request. Local workers inherit the operator process's network and
filesystem boundary; Jacobian does not widen it and does not claim to narrow it
without an external OS or container sandbox. No plugin or invocation may widen
budget, artifact, capability, or checker authority.

Exact enumeration, counterexample-guided refinement, constraint solving,
parameter sweeps, beam or tree search, evolutionary search, and agent-driven
loops are strategy plugins or examples. They do not introduce strategy-specific
records or trust rules into the generic kernel.

### Exit gate

Long-running experiments survive interruption and resumption, retain complete
lineage, feed independently verified counterexamples into later refinement,
and route nominated candidates through the verification boundary.
Sequential reference results are preserved across child-process failure,
cancellation, and resume. If multi-process scheduling is introduced, it must
preserve the same result and lineage. A new sealed plugin passes the generic
conformance suite without kernel or MCP changes. Concurrent or
transport-retried requests create one durable invocation. After process loss,
an invocation can be reconstructed without chat state and resumed without
losing or duplicating lineage. Workers cannot widen execution policy or
influence checker authorization.

## M4 — Conjecture workflows

Implementation status: the provisional hypothesis-transformation and
parameter-region promotion paths are in the repository. They remain pre-stable
and are not part of v0.2 conformance.

### Entry gate

Scalable search reliably records verified counterexamples, constructions, and
their exact transformation lineage.

### Objective

Give agents tools to turn verified counterexamples and constructions into
nearby statements, parameter families, and new experiments through the same
validation and falsification loop used by M3.

### Deliverables

- One typed hypothesis-transformation capability with repair, generation, and
  parameter-generalization operations
- Plugin-owned conjecture grammars and repair strategies rather than a
  kernel-level synthesis framework
- Deduplication within the active experiment or supplied reference set
- Exact proposed, sampled, sufficient, and necessary parameter-region labels;
  only independent checker records may use the verified labels
- Falsification pipelines for generated statements
- Explicit source and transformation records for every proposal
- Honest `UNKNOWN` novelty when no research-corpus provider is configured

### Exit gate

Every generated or repaired claim is explicitly labeled as a hypothesis and
can re-enter the ordinary validation, search, and verification pipeline.
Held-out evaluations confirm that failure to falsify a generated statement is
never reported as verification. Parameter claims distinguish proved, sampled,
and unknown regions. A synthetic plugin supports repair, generation, and
parameter generalization without core or MCP changes.

## M5 — Federated research corpus

### Entry gate

The search and conjecture tools have produced enough diverse verified and
failed experiments for retrieval quality and useful query patterns to be
measurable.

### Objective

Extend the implemented local research memory with cross-project mathematical
work without turning Jacobian into a monolithic knowledge platform or
confusing retrieval with proof.

### Deliverables

- Versioned research-episode export from the local episode database
- An optional reference provider rather than a required kernel dependency
- Structural, textual, metadata, ancestry, and temporal retrieval
- Trust, review, source, retraction, and availability labels
- Retention quotas, canonical deduplication, and curated promotion
- Provider-backed novelty checks with explicit corpus and cutoff scope
- Episode comparison and abstraction suggestions as optional hypothesis tools
- Certificate simplification as an independent checker-replay workflow

### Exit gate

The conjecture tools operate correctly with no provider configured. When a
provider is present, retrieval improves a held-out search or repair benchmark
while preserving trust labels and temporal cutoffs. Retrieved records and
suggested abstractions never gain verified status through ranking, clustering,
or ingestion.

## Stability target — v1.0 research platform

### Entry gate

Core schemas, checker registration, and artifact identities have remained
compatible across multiple problem domains and backend upgrades.

### Objective

Publish a stable, reproducible interface suitable for independent replication
and collaborative mathematical work.

### Deliverables

- Stable public artifact, result, and checker APIs
- Lean 4 and mathlib certificate verification
- Verified encoding bridges where practical
- Signed checker and certificate bundles
- Attribution, citation, review, and replication metadata
- Import/export formats for reproducible solver and proof artifacts
- Migration policy, compatibility test suite, and security review

### Exit gate

An independent installation can replay published result bundles from hashes and
obtain the same verified conclusion without importing the originating search
engine. Released wire formats, trust-root changes, and historical records pass
their compatibility and migration suites.

## Cross-cutting constraints

All releases preserve these invariants:

- Search output is evidence, not proof.
- A checker cannot be registered by the untrusted plugin it verifies.
- Artifact identity binds schema and semantics.
- Operational failure never silently changes a mathematical conclusion.
- Large outputs live behind resources rather than MCP tool responses.
- Claims of exhaustiveness identify an exact scope and carry replayable
  evidence.
- Future backends may extend assurance mechanisms without changing the meaning
  of older verified records.

The cross-release evidence plan is defined in:

- [Testing strategy](../reference/testing-strategy.md)
- [Performance benchmarks](../reference/performance-benchmarks.md)
- [Agent evaluations](../reference/agent-evaluations.md)
