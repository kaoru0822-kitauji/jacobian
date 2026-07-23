# Threat model

## Scope

This document defines the v0.1 threats to mathematical integrity, artifact
integrity, and service availability.

v0.1 accepts pure data plus operator-installed local plugins and checkers.
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

v0.1 plugins are operator-installed and trusted not to attack the host. They
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

## Trust assumptions

v0.1 assumes:

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

## Out of scope for v0.1

- Hostile executable plugin code
- Kernel or hypervisor compromise
- Side-channel resistance
- Multi-tenant authorization
- Remote identity and signing infrastructure
- Formal verification of the artifact store
- Proof that a formal statement matches informal mathematical intent

These exclusions must not be interpreted as mathematical assurance.
