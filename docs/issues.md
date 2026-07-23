# Proposed implementation issues

These are local, copy-ready drafts. They should be reviewed against the v0.1
specification before being posted to GitHub.

The issues build the generic kernel first and use two reference plugins only as
conformance tests. Domain-specific types do not enter the public core API.

## Posted issues

| Draft | GitHub |
| --- | --- |
| Issue 0 | [#1](https://github.com/morluto/jacobian/issues/1) |
| Issue 1 | [#2](https://github.com/morluto/jacobian/issues/2) |
| Issue 2 | [#3](https://github.com/morluto/jacobian/issues/3) |
| Issue 3 | [#4](https://github.com/morluto/jacobian/issues/4) |
| Issue 4 | [#5](https://github.com/morluto/jacobian/issues/5) |
| Issue 5 | [#6](https://github.com/morluto/jacobian/issues/6) |

Issues 6–10 remain local drafts until their dependencies are concrete.

## Issue 0

### Title

Adopt the v0.1 generic verification-kernel contract

### Body

#### Decision

Should Jacobian adopt `docs/specifications/v0.1.md` as its first normative
implementation contract?

#### Context

The repository currently has an architecture, tool-surface, roadmap, and
provisional later-release specifications, but no implementation. The first
decision should fix the trust boundary and scope before implementation issues
create accidental commitments.

Relevant documents:

- [v0.1 specification](https://github.com/morluto/jacobian/blob/main/docs/specifications/v0.1.md)
- [tool surface](https://github.com/morluto/jacobian/blob/main/docs/tools.md)
- [threat model](https://github.com/morluto/jacobian/blob/main/docs/threat-model.md)
- [v0.1 conformance specification](https://github.com/morluto/jacobian/blob/main/docs/conformance-v0.1.md)

The proposed v0.1 core exposes:

```text
artifact.put
claim.validate
evaluate.batch
witness.find
witness.verify
shrink.run
certificate.verify
```

Domain plugins provide mathematical semantics. Search and evaluation remain
untrusted; only operator-authorized witness and certificate checkers may
originate verified records.

#### Proposed decision

Accept the v0.1 specification with these constraints:

- the generic kernel contains no graph-, matrix-, solver-, or proof-specific
  types;
- at least two structurally different reference plugins must pass conformance;
- plugin manifests cannot authorize trusted checkers;
- operational failures remain separate from mathematical conclusions;
- representation transformation and structure search remain v0.2 work.

#### Alternatives

1. Build directly around the first graph/routing benchmark. This would produce
   a faster vertical slice but risks freezing domain assumptions into the API.
2. Design a universal mathematical intermediate representation first. This
   broadens the upfront scope without evidence that the abstraction will be
   useful.
3. Start with the small generic kernel and validate it using independent
   reference plugins. This is the proposed approach.

#### Acceptance criteria

- The public v0.1 tools and trust boundary are accepted or amended.
- The artifact, result, plugin, and checker contracts have named owners.
- Any unresolved question that blocks Issues 1–5 is recorded explicitly.
- Later-release specifications remain provisional.

#### Non-goals

- Selecting every future solver backend
- Finalizing v0.2 or later APIs
- Implementing the first plugin

## Dependency order

```text
0. adopt the v0.1 contract
    └── 1. schemas and result model
        ├── 2. artifact identity and storage
        ├── 3. plugin manifests and capabilities
        └── 4. checker registry
            └── 5. witness and certificate verification

1–5 ──► 6. evaluation and witness-search orchestration
1–6 ──► 7. checker-preserving shrinking
1–7 ──► 8. CLI and MCP adapter
1–8 ──► 9. graph/routing reference plugin
1–9 ──► 10. non-routing plugin and adversarial release gate
```

## Issue 1

### Title

Define the v0.1 artifact, claim, evidence, and result contracts

### Body

[Tracking decision: GitHub #1](https://github.com/morluto/jacobian/issues/1)

#### Current limitation

Jacobian does not yet have language-neutral contracts for mathematical objects
or tool results. Implementation cannot begin safely while operational failure,
mathematical conclusion, and verification assurance remain informal.

#### Desired outcome

Add versioned JSON Schemas and matching Python models for:

- canonical integers and rationals;
- artifact manifests;
- claims and domain references;
- candidates and objectives;
- witnesses and certificates;
- execution and input status;
- mathematical conclusions;
- assurance and verification records.

The result contract must keep execution, input validity, conclusion,
arithmetic, method, coverage, and verification status separate.

#### Success criteria

- Schemas reject JSON floating-point values in exact objects.
- Rationals require a reduced numerator and positive denominator and normalize
  zero to `0/1`.
- Timeout and error cannot deserialize as false or infeasible conclusions.
- Only authorized verification code can construct a verified result.
- Round-trip and malformed-input tests cover every schema.
- JSON Schema output is checked in or reproducibly generated.

#### Non-goals

- Domain-specific mathematics
- Artifact persistence
- MCP tools

## Issue 2

### Title

Implement domain-separated artifact identity and local content-addressed storage

### Body

[Tracking decision: GitHub #1](https://github.com/morluto/jacobian/issues/1)

#### Current limitation

Jacobian cannot persist or deduplicate mathematical objects, and hashing payload
bytes alone would permit schema or semantics confusion.

#### Desired outcome

Implement canonical encoding and an atomic local artifact store. Mathematical
object identity must bind:

```text
object format version
schema URI
semantics digest
canonicalizer digest
canonical bytes
```

Keep mathematical objects, manifests, and run metadata separate. Store blobs in
a digest-keyed filesystem and metadata in SQLite using WAL mode.

#### Success criteria

- Repeated canonical inputs produce the same object digest.
- Equivalent canonical rationals produce the same digest.
- The same payload under different schemas or semantics has different object
  identities.
- Blob insertion uses a staging file and atomic rename.
- Digest verification detects corrupted blobs.
- Concurrent insertion is idempotent.
- Storage quotas and maximum artifact sizes are configurable.

#### Non-goals

- S3 or distributed storage
- Research-memory indexes
- Curated knowledge records

## Issue 3

### Title

Define immutable plugin manifests and optional capability discovery

### Body

[Tracking decision: GitHub #1](https://github.com/morluto/jacobian/issues/1)

#### Current limitation

The kernel has no domain-independent way to discover which candidate codecs,
evaluators, witness oracles, reducers, or optional mathematical operations a
plugin supports.

#### Desired outcome

Define an immutable plugin manifest containing:

- plugin and domain identifiers;
- semantics and candidate schema URIs;
- supported witness schemas;
- capability names and implementation digests;
- compatibility and resource declarations.

Required capability interfaces should be small and optional:

```text
CandidateCodec
Evaluator
WitnessOracle
Reducer
SemanticEnumerator
CandidateEnumerator
Canonicalizer
Transformer
```

Trusted checker registration must not be part of the plugin manifest.

#### Success criteria

- A plugin can implement evaluation without mutation or canonicalization.
- Capability lookup is versioned and deterministic.
- Unsupported capabilities fail before execution.
- Plugin manifests cannot authorize checker code.
- No graph-, matrix-, solver-, or proof-specific type enters the generic
  manifest schema.

#### Non-goals

- Model-uploaded plugins
- Dependency installation
- Sandboxed execution

## Issue 4

### Title

Add an operator-managed checker registry and revocation model

### Body

[Tracking decision: GitHub #1](https://github.com/morluto/jacobian/issues/1)

#### Current limitation

There is no trusted mapping from witness or certificate formats to authorized
checker implementations. Allowing a plugin or caller to select arbitrary
executable code would let untrusted search code certify itself.

#### Desired outcome

Implement a registry binding checker identifiers and executable digests to:

- supported claim schema versions;
- supported semantics versions;
- supported witness or certificate formats;
- authorization and revocation state.

Registration and revocation are operator actions outside problem plugins.

#### Success criteria

- Unregistered and revoked checkers cannot originate verified records.
- A checker cannot verify unsupported claim or semantics versions.
- Registration and revocation are auditable.
- Historical records retain their checker identity.
- Policy distinguishes historical replay from new verification after
  revocation.

#### Non-goals

- Remote signing infrastructure
- Formal verification of checkers
- Plugin installation

## Issue 5

### Title

Implement generic witness and certificate verification dispatch

### Body

[Tracking decision: GitHub #1](https://github.com/morluto/jacobian/issues/1)

#### Current limitation

The kernel cannot independently replay witnesses or route self-describing
certificates through authorized checkers.

#### Desired outcome

Implement `witness.verify` and `certificate.verify`.

Witness verification binds:

```text
claim
semantics
candidate
witness
checker
```

Certificate verification additionally supports optional encoding and payload
digests. The certificate format and trust registry determine the checker;
callers cannot provide executable checker code.

v0.1 must support direct finite witnesses and complete finite enumeration
certificates through reference checkers.

#### Success criteria

- A witness outside its declared domain is rejected.
- A certificate copied to another claim or candidate is rejected.
- An unsupported certificate format remains unverified.
- Checker output uses the common result envelope.
- Verification packages do not import search evaluators or witness oracles.

#### Non-goals

- SAT, LP, or Lean certificate implementations
- Informal-to-formal correspondence checking
- Global candidate minimality

## Issue 6

### Title

Add generic batched evaluation and adversarial witness-search orchestration

### Body

#### Current limitation

Models cannot evaluate candidate batches or request structured defeating
witnesses through a domain-independent kernel API.

#### Desired outcome

Implement `evaluate.batch` and `witness.find` over plugin capabilities.

Evaluation returns:

- objective vectors;
- proposed witnesses;
- arithmetic and coverage;
- features and failure classifications;
- evidence and trace URIs;
- evaluator and environment provenance.

Witness search returns `FOUND`, `NONE_CERTIFIED`, `SEARCH_EXHAUSTED`,
`NOT_FOUND_WITHIN_SCOPE`, or `UNKNOWN`. `NONE_CERTIFIED` is permitted only when
the response references a successful `certificate.verify` record. Exhausted
search may produce a proposed certificate but cannot certify itself.

#### Success criteria

- Several candidates can be evaluated in one request.
- Cache keys bind claim, semantics, candidate, evaluator, profile, and
  environment.
- Timeout and error preserve an unknown conclusion.
- Large traces are stored as artifacts.
- Evaluation always reports `verification = UNVERIFIED`.
- A found witness can be passed unchanged to `witness.verify`.

#### Non-goals

- Search algorithms
- Distributed workers
- Generic solver invocation

## Issue 7

### Title

Minimize plugin-defined candidates and witnesses with checked reductions

### Body

#### Current limitation

Large candidates and witnesses are difficult to understand, and there is no
generic way to reduce them while preserving a checked predicate.

#### Desired outcome

Implement `shrink.run` using plugin-provided reducers and an
operator-authorized preservation checker.

Initially support:

```text
target_kind = candidate
target_kind = witness
```

Every accepted step must be replayed. Report minimality as none, local,
one-step, bounded-global, or proved-global.

#### Success criteria

- The shrink trace records accepted and rejected proposals.
- The final target has a fresh verification record.
- A reducer that breaks the predicate cannot have its output accepted.
- Global minimality requires a checked completeness certificate.
- Reducers and objectives are defined through versioned plugin schemas.

#### Non-goals

- Certificate simplification
- Learned reducers
- Domain-specific reduction rules in the kernel

## Issue 8

### Title

Expose the verification kernel through a CLI and thin MCP adapter

### Body

#### Current limitation

The kernel contracts are not accessible through a normal command-line
interface or MCP without duplicating orchestration logic.

#### Desired outcome

Add a Python CLI and MCP adapter exposing:

```text
artifact.put
claim.validate
evaluate.batch
witness.find
witness.verify
shrink.run
certificate.verify
```

Optional domain tools are registered only when the selected plugin supports
them. Large artifacts are MCP resources; tool responses contain compact
structured content and URIs.

#### Success criteria

- CLI and MCP call the same kernel API.
- Every tool has generated input and output schemas.
- Local stdio transport works in integration tests.
- The adapter contains no domain mathematics.
- MCP cancellation maps to kernel cancellation where supported.
- MCP SDK dependencies remain isolated from core schemas.

#### Non-goals

- Remote authentication
- Streamable HTTP deployment
- Persistent background search jobs
- Experimental MCP task APIs

## Issue 9

### Title

Validate semantic closure and hidden witnesses with a graph-routing plugin

### Body

#### Current limitation

The generic interfaces have not been exercised by a domain where the complete
semantic family differs from a designer's intended objects.

#### Desired outcome

Implement the graph/routing reference plugin described in
`docs/benchmarks.md`, including:

- pure-data graph, flow, path, and routing schemas;
- an evaluator and witness oracle;
- explicit bounded semantic-family materialization;
- structured hidden-path and routing witnesses;
- independent witness and finite-enumeration checkers;
- domain-specific reducers.

#### Success criteria

- Hidden legal paths omitted from an intended list are found.
- Enumeration limits cannot report exhaustive coverage.
- Returned witnesses replay through the independent checker.
- The plugin uses only generic artifact, result, and capability contracts.
- No routing-specific type is added to the kernel package.

#### Non-goals

- Generic graph ontology
- Isomorphism-free discovery
- Polyhedral transformation

## Issue 10

### Title

Validate cross-domain generality and fail-closed behavior before v0.1

### Body

#### Current limitation

A single graph-oriented plugin cannot show that the capability API is general,
and happy-path replay does not demonstrate fail-closed behavior.

#### Desired outcome

Implement a bounded matrix or other non-routing reference plugin and a
cross-domain conformance suite. The second plugin must use different candidate,
witness, and reduction shapes from the graph/routing plugin.

The adversarial suite covers:

- false exhaustive flags;
- malformed exact values;
- schema and semantics confusion;
- certificate binding mismatches;
- corrupted blobs;
- timeout-as-false conversion;
- stale cache entries;
- untrusted checker registration;
- reductions that break the predicate.

#### Success criteria

- Both plugins use the same unmodified generic core API.
- Every injected attack is rejected or remains explicitly unverified.
- Tests exercise public kernel behavior rather than private helper names.
- Clean-process replay reproduces both verified reference results.
- The v0.1 API is not declared stable until this suite passes.

#### Non-goals

- Distributed-system fault injection
- Sandbox penetration testing
- Formal proof of the kernel implementation

## Provisional v0.2 epics

Do not post these as implementation issues until the v0.1 conformance gate
passes:

1. Run bounded candidate enumeration as persistent experiments.
2. Add structure canonicalization and auditable enumeration scope.
3. Propose and independently verify representation transformations.
4. Generate and check exact rational polyhedral separators.
5. Exercise bounded discovery in both reference domains.
