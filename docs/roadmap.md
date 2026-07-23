# Roadmap

## Release and milestone policy

Each milestone is gated by evidence, not by a calendar date. Later milestone
work does not begin until the preceding trust and compatibility gates pass.

v0.2 is the current and only supported pre-stable alpha contract. M3 through
M5 are capability milestones, not promised package versions or compatibility
releases. Their scope and APIs may change. v1.0 remains a stability target
rather than the next scheduled release.

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

### Entry gate

Bounded enumeration and transformation APIs have proved useful in two different
domains.

### Objective

Run large heuristic and adversarial searches inside the engine while retaining
lineage, failure evidence, and exact-verification boundaries.

### Deliverables

- Evolutionary/program search
- Counterexample-guided inductive synthesis
- Tree, beam, or best-first search
- Pareto and novelty archives
- Compiled semantic families using BDDs, ZDDs, automata, dynamic programs, or
  oracles
- Resumable and cancellable experiments
- Local multi-process execution followed by distributed workers when justified
- Resource-bounded local execution for operator-approved generated candidate
  code, without claiming a security sandbox

### Exit gate

Long-running experiments survive interruption and resumption, retain complete
lineage, and route promoted candidates through the verification boundary.
Sequential reference results are preserved under multi-process execution,
worker failure, cancellation, and resume.

## M4 — Conjecture workflows

### Entry gate

Scalable search reliably records verified counterexamples, constructions, and
their exact transformation lineage.

### Objective

Give agents tools to turn verified counterexamples and constructions into
nearby statements, parameter families, and new experiments.

### Deliverables

- Conjecture repair across assumptions, constants, domains, and conclusions
- Candidate conjecture generation under typed grammars
- Deduplication within the active experiment or supplied reference set
- Exact or certified parameter-region extraction
- Falsification pipelines for generated statements
- Explicit source and transformation records for every proposal
- Honest `UNKNOWN` novelty when no research-corpus provider is configured

### Exit gate

Every generated or repaired claim is explicitly labeled as a hypothesis and
can re-enter the ordinary validation, search, and verification pipeline.
Held-out evaluations confirm that failure to falsify a generated statement is
never reported as verification. Parameter claims distinguish proved, sampled,
and unknown regions.

## M5 — Research corpus integration

### Entry gate

The search and conjecture tools have produced enough diverse verified and
failed experiments for retrieval quality and useful query patterns to be
measurable.

### Objective

Let agents retrieve prior mathematical work without turning Jacobian into a
monolithic knowledge platform or confusing retrieval with proof.

### Deliverables

- A versioned research-episode export and provider interface
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

- [Testing strategy](testing-strategy.md)
- [Performance benchmarks](performance-benchmarks.md)
- [Agent evaluations](agent-evaluations.md)
