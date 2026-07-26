# Threat model

[Documentation home](../index.md)

- Status: Current
- Host boundary: Operator-installed code is trusted not to attack the machine
- Related record: [Architecture](architecture.md)

## Scope

This document covers Jacobian's capability surface, local and remote hosts,
artifact store, domain plugins, and independent checkers. Every installed
capability and future adapter must preserve these mathematical and
artifact-integrity boundaries.

The kernel owns trust and execution policy — artifact identity, execution
status, assurance, checker authorization, budgets, and provenance — not
mathematical strategy. Namespaced capability adapters expose a broad portfolio
of operations; domain plugins own mathematical semantics; agents compose
operations into research strategies. The independent checker boundary is
unchanged across these layers: search, generation, evaluation, and
transformation output never self-certifies, and `VERIFIED` requires an
operator-authorized checker independent of the proposing, searching, or
evaluating implementation.

The implemented code accepts pure data plus operator-installed local plugins
and checkers.
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
- durable search lineage that cannot be silently rebound to another request,
  plugin, runtime, checkpoint, or experiment;
- parameter-region promotion bound to the exact subject and claim artifacts,
  not merely an equal payload.
- durable workspace lineage that cannot be silently rebound to another
  workspace, branch, base revision, or idempotency request;
- remote tenant separation for artifacts, episodes, workspaces, experiments,
  plugins, and checker metadata.

Availability is important but secondary to integrity: resource exhaustion may
produce timeout or error, never a false mathematical conclusion.

## Adversaries and failure sources

### Mathematically untrusted problem plugin

Plugins are operator-installed and trusted not to attack the host. They are not
trusted to establish mathematical truth. A plugin may:

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
- installation snapshots bind every regular file in the plugin package,
  capability contracts, runtime/build identity, and platform identity;
  discovery measures packages without importing them, and workers reject
  bytecode-only or compiled package modules;
- plugin workers have bounded process/output lifetime for operational
  containment, but run locally with the operator's environment and are not a
  security sandbox; network and filesystem authority are inherited from the
  operator process and must be narrowed by an OS or container policy when
  required;
- reference plugins are tested against adversarial fixtures.

The deliberate crash, malformed-output, and timeout behaviors used by the
generic conformance kit exist only in a disposable synthetic package and
isolated state. They are not a required production-plugin interface.

### Agent-authored workspace state

A model or remote caller may record a false claim, report an unsuccessful
attempt as complete, cite a missing dependency, create a reference cycle, reuse
an idempotency key for different content, write from a stale branch head, forge
a lifecycle label, or create a cyclic supersession chain.

Controls:

- workspace drafts expose no caller-controlled verified or derived-stale field;
- stored findings, attempts, and lifecycle marks are explicitly agent-authored
  and unverified;
- explicit finding references must exist in the same workspace branch;
- only `workspace.open` may create the branch's singular canonical problem
  card;
- new dependency cycles, supersession cycles, self-supersession, and
  assumption-kind mismatches are rejected;
- an invalidating `RETRACTED` or `SUPERSEDED` mark cannot be silently cleared
  by `CLOSED` or `ARCHIVED`; an explicit `ACTIVE` restoration is required;
- `COMPLETED` attempts do not close goals; only an explicit `CLOSED` mark changes
  workflow state, and this never assigns a mathematical conclusion;
- stale warnings derive only from current `RETRACTED` or `SUPERSEDED` roots and
  explicit dependency or assumption links; absence of a warning says nothing
  about semantic completeness or truth;
- every mutation binds an exact request digest to an idempotency key;
- branch-head comparison and indexed writes commit in one SQLite transaction;
- each query uses one SQLite read snapshot, and accepted row order rather than
  caller-controlled timestamps selects current marks and recent entries;
- immutable revision artifacts bind the accepted parent lineage;
- workspace retrieval, context packs, focus, marks, and attempt outcomes never
  authorize a checker or promote assurance.

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
- validation before persistence, including registered model-backed cross-field
  invariants when ordering or derived digests cannot be expressed in JSON
  Schema alone;
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
- any capability or workflow that relies on a verified result replays the cited
  verification record with its authorized checker and requires the reproduced
  record identity;
- parameter-region promotion requires the exact subject and declared claim
  artifact URIs in the verification record's parents; equal object digests in
  different artifact carriers are insufficient;
- no caller-controlled checker executable.

### SAT source or projection substitution

An assignment or proof may name another CNF, reuse a variable map with changed
clauses, change literal numbering, or relabel proof bytes under another format
version.

Controls:

- canonical CNF artifacts bind the ordered variable map and deterministic
  DIMACS projection by digest;
- assignment and raw proof artifacts bind the exact CNF artifact URI, object
  and payload digests, variable-map and DIMACS digests, projection version,
  full scope, producer runtime, and resource budget;
- evidence artifacts retain the exact CNF as a parent;
- assignment and raw proof storage remains unverified;
- `sat.model.verify` re-derives the assignment binding before dispatch, then a
  standard-library-only clean-process checker independently validates the
  canonical CNF, payload, variable-map and DIMACS digests, assignment,
  evidence bindings, and lineage before evaluating every clause;
- SAT assignment checker requests expose exact artifact payload digests and
  parent lineage in addition to object, schema, and semantics identities; and
- a rejected assignment, malformed input, timeout, or checker failure remains
  `UNKNOWN` and never establishes UNSAT.

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
limits. Durable metadata may also be truncated, malformed, or internally
inconsistent after a storage or software failure.

Controls:

- execution status is orthogonal to conclusion;
- incomplete writes use staging paths and atomic commit;
- idempotency keys select one durable capability invocation, append-only event
  chains preserve retries and runtime identity, and interrupted invocations
  recover from immutable checkpoints;
- workspace idempotency keys select one accepted mutation, and optimistic
  revision conflicts leave indexed workspace state unchanged;
- recovery validates a snapshot against its database key and indexed state;
  malformed rows are quarantined as `ERROR` without stopping unrelated
  recovery;
- checkpoint restoration rebinds request, package snapshot, implementation,
  environment, budget, archive, and accounting identity before opaque strategy
  state is reused;
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

### Degree-sequence realization

The NetworkX construction backend may return a malformed graph, mishandle a
sequence, or propose an invalid non-graphical obstruction.

Controls:

- construction and obstruction discovery never self-promote;
- the certificate binds the exact sorted sequence and either the explicit
  graph or one basic/Erdős–Gallai obstruction;
- the authorized checker uses only the Python standard library and does not
  import NetworkX or the proposing adapter;
- the checker recomputes simplicity, vertex degrees, parity, maximum-degree
  bounds, and the claimed Erdős–Gallai inequality;
- changed edges, degrees, inequality parameters, or bindings are rejected.

### Remote client or tenant

A remote caller may omit authentication, present an invalid token, choose a
malicious tenant string, guess another tenant's content-addressed URI, or try
to use an adapter to self-promote evidence.

Controls:

- remote transports fail closed unless a token file is configured or the
  operator explicitly selects anonymous development mode;
- opaque tokens are compared in constant time and bind an authenticated
  subject plus required scope;
- tenant IDs are syntax-checked and hashed before they contribute to a state
  path;
- tool and resource handlers route through the same authenticated subject;
- each subject receives a separate artifact store and SQLite metadata
  database;
- capability adapters cannot return verified assurance without a valid
  verification record, complete bound parent set, and matching conclusion in
  that tenant's store;
- workspace tools use the same subject-routed kernel and tenant-local state
  database as capability and artifact operations;
- TLS, rate limits, host isolation, and network policy are supplied by the
  deployment platform.

Static bearer tokens do not provide rotation without restart, delegated
authorization, user consent, or a full identity lifecycle. They are an initial
controlled-deployment mechanism. Hosted deployments should replace the token
verifier with OAuth/OIDC while retaining subject-bound tenant routing.

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

An optional research-corpus provider is treated as an untrusted accelerator.
It may omit relevant work, return poisoned or retracted records, violate an
expected ranking policy, or attempt to relabel evidence. Provider responses
therefore carry source, corpus, temporal-cutoff, review, retraction, and
verification metadata; Jacobian independently resolves local artifacts and
verification records. The provider cannot authorize checkers or write verified
results, and its absence must not disable local capability discovery,
invocation, artifact access, or verification replay.

## Out of scope

- Hostile executable plugin code
- Kernel or hypervisor compromise
- Side-channel resistance
- Hosted OAuth/OIDC lifecycle and remote signing infrastructure
- Distributed worker leases or multiple active Jacobian coordinators sharing a
  state directory
- Formal verification of the artifact store
- Proof that a formal statement matches informal mathematical intent

These exclusions must not be interpreted as mathematical assurance.
