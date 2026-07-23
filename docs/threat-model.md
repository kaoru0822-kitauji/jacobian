# Threat model

## Scope

This document defines the v0.2 threats to mathematical integrity,
artifact integrity, and service availability.

The implemented releases accept pure data plus operator-installed local
plugins and checkers.
Jacobian does not provide a security sandbox. Code installed by the operator is
assumed safe to execute on that machine.

## Protected properties

Jacobian protects:

- the binding between a formal claim and its semantics;
- the identity and immutability of stored artifacts;
- the binding between evidence and the exact claim, candidate, scope, and
  encoding it concerns;
- the authorization state and identity of checkers;
- the distinction between unverified evidence and verified results;
- the distinction between execution state and mathematical conclusion;
- reproducible replay of completed verification records.

Availability is important but secondary to integrity: resource exhaustion may
produce timeout or error, never a false mathematical conclusion.

## Adversaries and failure sources

### Mathematically untrusted problem plugin

v0.2 plugins are operator-installed and trusted not to attack the host. They
are not trusted to establish mathematical truth. A plugin may:

- omit legal semantic objects;
- misreport arithmetic or coverage;
- return a malformed or irrelevant witness;
- label a bounded search exhaustive;
- attempt to register its own checker;
- construct cache keys that hide a semantics change.

Controls:

- plugin output remains unverified;
- checker authorization is outside plugin manifests;
- evidence binds claim, semantics, candidate, and scope;
- plugin workers have bounded process/output lifetime for operational
  containment, but run locally with the operator's environment and are not a
  security sandbox;
- reference plugins are tested against adversarial fixtures.

### Malformed or ambiguous artifact

An artifact may:

- contain invalid or noncanonical exact values;
- exploit duplicate keys or inconsistent Unicode;
- use the same bytes under another schema;
- reference missing or cyclic dependencies;
- exceed parser, memory, or storage limits.

Controls:

- constrained versioned canonical encoding;
- domain-separated object identity;
- validation before persistence;
- size, depth, and dependency limits;
- digest verification on read.

### Evidence substitution

An otherwise valid witness or certificate may be replayed against:

- another claim;
- another semantics version;
- another candidate;
- another encoding;
- another scope.

Controls:

- explicit digest bindings in evidence;
- checker-side binding validation before mathematical replay;
- no caller-controlled checker executable.

### Buggy or compromised checker

An authorized checker may contain a defect or later become untrusted.

Controls:

- small checker packages isolated from search code;
- immutable executable digests;
- authorization and revocation records;
- adversarial and differential tests;
- optional independent implementations or formal kernels for higher assurance;
- historical records retain the checker identity used.

Checker authorization narrows the trusted computing base; it does not prove the
checker correct.

### Cache poisoning

A stale result may be reused after changing:

- claim or semantics;
- candidate;
- evaluator or checker;
- scope or limits;
- environment affecting the computation.

Controls:

- cache keys bind every semantics-relevant digest and parameter;
- verified records are never inferred from unverified cache entries;
- cache entries are validated against current artifact digests.

### Operational failure

Processes may time out, crash, be cancelled, lose output, or exceed resource
limits.

Controls:

- execution status is orthogonal to conclusion;
- incomplete writes use staging paths and atomic commit;
- reached limits downgrade coverage;
- tool errors cannot be translated into false, infeasible, or exhaustive.

### Faulty enumeration or canonicalization

A domain enumerator may omit candidates, change scope between pages, repeat a
cursor, exceed the requested page, or falsely claim completion. A
canonicalizer may collide non-isomorphic structures or change across runs.

Controls:

- page progress, page size, cursor advancement, and scope stability are
  validated;
- candidate, wall-time, cancellation, and operational limits preserve bounded
  coverage;
- search snapshots never self-certify;
- canonical keys bind the canonical mathematical object to the exact
  canonicalizer implementation digest;
- any negative theorem based on enumeration requires a separate authorized
  completeness checker.

### Representation substitution

A proposed transformation may bind the wrong source or target, strengthen a
relaxation into equivalence, or change its proof obligation after generation.

Controls:

- transformation evidence binds both schemas, both semantics digests, both
  object digests, relation, obligation digest, and transformer digest;
- transformer output remains unverified;
- an independently authorized checker selects on format plus source and target
  compatibility and creates a separate immutable verification record.

### Solver-generated false evidence

The exact-rational solver backend may be buggy, time out, or return a model
that does not satisfy the intended mathematics.

Controls:

- solver status never directly becomes verified;
- membership weights and separators are self-describing artifacts;
- a checker that does not import Z3 or the generator replays every rational
  equality and inequality;
- changed coefficients, margins, bindings, or scopes are rejected.

## Trust assumptions

The implemented releases assume:

- SHA-256 collision resistance;
- correct operation of the host filesystem and SQLite within their documented
  guarantees;
- an operator controls checker authorization;
- an operator installs only plugin and checker code considered safe to execute
  on the host;
- the Python runtime and checker dependencies are part of the checker trusted
  computing base;
- formal claims and semantics have been reviewed to the degree recorded in
  their provenance.

The system does not assume that an evaluator, solver, model, plugin, retrieved
research record, or search policy is correct.

## Out of scope for v0.2

- Hostile executable plugin code
- Kernel or hypervisor compromise
- Side-channel resistance
- Multi-tenant authorization
- Remote identity and signing infrastructure
- Formal verification of the artifact store
- Proof that a formal statement matches informal mathematical intent

These exclusions must not be interpreted as mathematical assurance.
