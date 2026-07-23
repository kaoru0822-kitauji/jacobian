# Roadmap

## Release policy

Each release is gated by evidence, not by a calendar date. A later release does
not begin until the preceding release's trust and compatibility gates pass.

v0.1 is normative. v0.2 through v1.0 are provisional plans whose APIs may
change.

## v0.1 — Verification kernel

### Objective

Demonstrate that a bounded mathematical candidate can be stored, attacked,
shrunk, and independently verified without trusting its search implementation.

### Deliverables

- Versioned claim, candidate, witness, certificate, and result schemas
- Canonical artifact encoding and domain-separated hashing
- Digest-keyed local artifact store and SQLite run metadata
- Operator-managed checker registry
- Seven generic MCP tools
- A generic plugin capability API
- At least two structurally different reference plugins and replay checkers
- CLI and thin MCP adapter
- Adversarial fail-closed test suite

### Exit gate

Both reference plugins replay exact certificates, return independently verified
failure witnesses, and reject deliberately corrupted evidence.

## v0.2 — Bounded discovery

### Entry gate

- v0.1 artifact and result schemas have survived both reference-plugin
  adversarial suites.

### Objective

Move from verifying supplied candidates to exhaustively searching bounded
candidate classes and verifying representation changes.

### Deliverables

- Bounded enumeration experiments
- Search-safe canonicalization and symmetry rejection
- Transformation proposal and independent transformation verification
- Exact polyhedral projection and separation
- Persistent experiment handles and cancellation
- Bounded-discovery workflows exercised in both v0.1 reference plugins

### Exit gate

A bounded search produces a candidate archive with auditable scope, and at
least one representation transformation and exact separator are independently
verified.

## v0.3 — Scalable search

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
- Sandboxed model-generated candidate code

### Exit gate

Long-running experiments survive interruption and resumption, retain complete
lineage, and route promoted candidates through the v0.1 verification boundary.

## v0.4 — Research memory

### Entry gate

The system has accumulated enough verified and failed experiments for retrieval
quality to be measurable.

### Objective

Turn experiment history into useful, trust-labeled research memory without
confusing retrieval or clustering with proof.

### Deliverables

- Structural and textual experiment retrieval
- Trust and review labels
- Failure clustering and episode comparison
- Suggested abstraction and motif extraction
- Certificate simplification
- Retention quotas, deduplication, and curated promotion
- Temporal availability metadata

### Exit gate

Retrieval improves a held-out search benchmark while never upgrading unverified
records into certified conclusions.

## v0.5 — Conjecture development

### Entry gate

Memory and transformation records are reliable enough to guide new experiments.

### Objective

Turn verified counterexamples and constructions into nearby statements,
parameter families, and new research questions.

### Deliverables

- Conjecture repair across assumptions, constants, domains, and conclusions
- Candidate conjecture generation and deduplication
- Exact or certified parameter-region extraction
- Novelty checks against the temporal knowledge base
- Falsification pipelines for generated statements

### Exit gate

Every generated or repaired claim is explicitly labeled as a hypothesis and can
re-enter the ordinary validation, search, and verification pipeline.

## v1.0 — Stable research platform

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
engine.

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
