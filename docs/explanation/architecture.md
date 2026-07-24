# Architecture

[Documentation home](../index.md)

- Status: Current design map for v0.2 and the provisional M3/M4 implementation
- Normative sources:
  [v0.2 specification](../reference/specifications/v0.2.md) and
  [conformance gate](../reference/conformance-v0.2.md)

## Purpose

Jacobian gives agents reusable mathematical capabilities and durable research
memory while separating mathematical discovery from mathematical trust. The
[capability-first product blueprint](product-blueprint.md) defines the
model-facing product direction; this document describes the underlying kernel
and trust zones.

Models, search algorithms, and domain solvers are allowed to be heuristic,
stochastic, incomplete, and frequently replaced. Verification is performed by
small, operator-authorized checkers against versioned formal claims and domain
semantics.

The agent-facing product has two lanes:

```text
agent
  │
  ├── EXPLORE ──► retrieval, computation, search, solver, candidate, witness
  │                    │
  │                    └── HEURISTIC or COMPUTED + research episode
  │
  └── VERIFY  ──► the same capability + authorized checker/proof engine
                       │
                       └── VERIFIED + immutable verification record
```

The durable trust contract behind the optional verification lane is:

```text
informal statement
    │ human or formal correspondence review
    ▼
formal ClaimSpec + versioned DomainSemantics
    │
    ├── untrusted generation, transformation, search, and evaluation
    │                         │
    │                         ▼
    │                candidate + witness/certificate
    │                         │
    └─────────────────────────┴──► authorized independent checker
                                      │
                                      ▼
                                  VerifiedResult
```

The formal claim may still be a poor translation of the informal conjecture.
Jacobian records that correspondence and its review status; it does not pretend
that schema validation can establish it automatically.

The v0.2 kernel and bounded-discovery behavior are the current release
contract. Sections describing resumable strategy search and conjecture
workflows document provisional M3/M4 implementations and do not extend v0.2
conformance.

## Trust zones

### Trusted inputs and services

- Versioned claim schemas
- Versioned domain semantics
- The checker registry
- Operator-authorized witness, certificate, and transformation checkers
- The artifact identity and certificate-binding implementation

### Untrusted accelerators

- Candidate generators and mutators
- Heuristic and exact-candidate evaluators
- Witness oracles
- Structure enumerators and canonicalizers used for search
- Representation transformers
- SAT, SMT, LP, MIP, and polyhedral solvers
- Language-model output
- Operator-installed plugin code as a source of mathematical claims

A solver or evaluator can produce evidence. It cannot promote its own evidence
to `VERIFIED`.

## Core records

Jacobian separates four kinds of state.

### Mathematical object

An immutable object encoded using a versioned schema and canonicalizer.

```text
object_digest = SHA256(
    object_format_version
    || schema_uri
    || semantics_uri
    || canonicalizer_digest
    || canonical_bytes
)
```

This domain-separated digest prevents the same bytes from silently acquiring a
different meaning under another schema or semantics version.

### Artifact manifest

An immutable, content-addressed record connecting an object to its media type,
schema, parent artifacts, and a short summary.

Object identity and artifact identity answer different questions. The object
digest binds canonical payload, schema, semantics, and canonicalizer. The
artifact URI also binds carrier metadata such as parents and summary. Code that
authorizes replay or promotion must require the exact artifact URI when lineage
matters; equal object digests do not make two carriers interchangeable.

### Run record

Execution metadata such as runtime, seed, environment, limits, logs, and tool
version. A run record does not change the identity of the mathematical object.
v0.2 persists verification records and bounded-enumeration snapshots. The
provisional M3 runtime adds append-only lifecycle events, immutable strategy
checkpoints, archive pages, and archive manifests around one mutable snapshot
index.

### Research episode

An immutable, locally indexed record of one capability request and result,
including adapter version, mode, assurance, artifact lineage, summary, tags,
and timestamp. Raw runs never become trusted knowledge merely because they
were stored, indexed, retrieved, or reviewed. Source artifacts and
verification records remain immutable.

## Research memory and optional corpus integration

Jacobian's research memory and experiment ledger are part of the workbench:
they preserve local episodes, lineage, and evidence needed to retrieve, resume,
and replay work. Corpus-scale ranking and cross-project retrieval are separate,
optional capabilities:

```text
agent
  │ MCP tools
  ▼
Jacobian capabilities and local research memory
  │                         ▲
  │ versioned episodes      │ trust-labeled retrieval
  ▼                         │
optional research-corpus provider
```

The local `knowledge.search` adapter and any external provider may suggest
records, motifs, or hypotheses. Retrieval is outside the verification trust
boundary and cannot mutate artifacts, register checkers, or promote evidence.
All local workflows remain available when no provider is configured.

## Model-facing capability API

`CapabilityService` is a registry of operator-installed adapters. Each adapter
declares a stable operation ID, version, supported `EXPLORE` and `VERIFY`
modes, input and output JSON Schemas, and discovery metadata. The MCP
projection exposes the registry through `capability://catalog` and
`capability.invoke`, so a new Alloy, Lean, SAT/SMT, CAS, or domain adapter does
not require another MCP tool or a generic-core type.

The service validates both schemas and prevents adapters from self-promoting:
`VERIFIED` requires a valid local verification record whose checked evidence
is returned with the capability result.

## Common result model

Operational state, mathematical conclusion, and assurance are orthogonal:

```json
{
  "execution": {
    "status": "COMPLETED",
    "runtime_ms": 1240
  },
  "input": {
    "status": "ACCEPTED"
  },
  "claim_digest": "sha256:...",
  "candidate_digest": "sha256:...",
  "conclusion": "FALSE",
  "assurance": {
    "arithmetic": "EXACT_INTEGER",
    "method": "DIRECT_WITNESS",
    "coverage": "NOT_APPLICABLE",
    "verification": "VERIFIED",
    "checker_digest": "sha256:...",
    "scope_uri": "artifact://sha256/..."
  },
  "evidence_uris": ["artifact://sha256/..."],
  "trace_uri": "artifact://sha256/..."
}
```

Required enums:

```text
execution.status:
    COMPLETED | TIMEOUT | CANCELLED | ERROR

input.status:
    ACCEPTED | REJECTED

conclusion:
    TRUE | FALSE | UNKNOWN | NOT_APPLICABLE

arithmetic:
    EXACT_INTEGER
    EXACT_RATIONAL
    EXACT_ALGEBRAIC
    VERIFIED_INTERVAL
    SYMBOLIC
    FLOATING_HEURISTIC

method:
    DIRECT_WITNESS
    EXHAUSTIVE_FINITE
    CHECKED_CERTIFICATE
    BOUNDED_SEARCH
    SAMPLING
    HEURISTIC

coverage:
    EXHAUSTIVE
    BOUNDED
    RESTRICTED
    SAMPLED
    NOT_APPLICABLE

verification:
    UNVERIFIED | VERIFIED
```

Only authorized verification tools may return `verification = VERIFIED`.
`TIMEOUT` and `ERROR` are execution states, not mathematical conclusions.
A verified result is not limited to rational exhaustive enumeration:
kernel-checked symbolic proofs, exact algebraic certificates, and
outward-rounded interval certificates are valid assurance mechanisms when an
authorized checker replays them. Such proof certificates may use
`coverage = NOT_APPLICABLE`; direct finite enumeration must instead report
`EXHAUSTIVE`.

## Plugin capabilities

Domains implement small optional capabilities instead of one mandatory
`ProblemPlugin` interface:

```python
class ProblemSpec(Protocol):
    ...

class CandidateCodec(Protocol):
    def validate(self, candidate: JSON) -> None: ...
    def canonicalize(self, candidate: JSON) -> bytes: ...

class Evaluator(Protocol):
    def evaluate(self, candidate: JSON, profile: str) -> Evaluation: ...

class WitnessOracle(Protocol):
    def find(self, candidate: JSON, budget: Budget) -> WitnessSearch: ...

class WitnessChecker(Protocol):
    def verify(self, candidate: JSON, witness: JSON) -> Verification: ...

class Reducer(Protocol):
    def reductions(self, target: JSON) -> Iterable[JSON]: ...

class SemanticEnumerator(Protocol):
    def enumerate_family(
        self, candidate: JSON, family: JSON
    ) -> Iterable[JSON]: ...

class CandidateEnumerator(Protocol):
    def enumerate_candidates(self, bounds: JSON) -> Iterable[JSON]: ...

class Transformer(Protocol):
    def transform(
        self, source: JSON, target_kind: str
    ) -> Transformation: ...

class TransformationChecker(Protocol):
    def verify(self, transformation: Transformation) -> Verification: ...

class CertificateChecker(Protocol):
    def verify(self, certificate: JSON) -> Verification: ...

class Proposer(Protocol):
    def propose(self, request: SearchProposalRequest) -> SearchProposal: ...

class Refiner(Protocol):
    def refine(self, request: SearchRefinementRequest) -> SearchRefinement: ...

class HypothesisTransformer(Protocol):
    def transform(
        self, request: HypothesisRequest
    ) -> HypothesisResponse: ...
```

Search plugins cannot register themselves as trusted checkers. The checker
registry is operator-managed and binds checker digests to supported claim,
semantics, and certificate versions.

### Sealed plugin identity

Installation creates one immutable registry snapshot that binds the manifest,
capability entrypoints, each implementation package digest, runtime and build
identity, and platform compatibility. Discovery inspects source files without
importing the package. Capability resolution remeasures the package before
execution, so a changed file cannot continue under the installed snapshot.

The initial package format hashes regular package files, while declared and
imported modules must be Python source. Symlinks, traversal outside the
package, bytecode-only module execution, and native extension-module execution
are rejected. This protects registry identity; it does not sandbox
operator-installed code once a worker executes it.

The generic fault matrix runs against a disposable, conformance-only package in
isolated state. Production plugins are not expected to expose inputs that
deliberately crash, hang, or emit malformed responses.

## Search and checker separation

The independent checker may share stable wire schemas and primitive exact
arithmetic types with the search side. It must not import the search evaluator,
oracle, canonicalizer, or solver integration.

Higher assurance may add a second implementation using a different algorithm or
a proof-assistant kernel. Different programming languages are useful for
defense in depth, but language diversity alone does not establish mathematical
independence.

## Bounded discovery

`search.enumerate` validates a claim and the plugin's optional enumerator,
evaluator, and canonicalizer capabilities before creating a durable experiment
handle. The local worker pages through a declared scope, commits candidate and
evaluation artifacts, and maintains exact accounting:

```text
enumerator page
    → schema validation
    → optional implementation-bound canonical key
    → duplicate rejection
    → batch evaluation
    → immutable archive page
    → durable snapshot
```

The snapshot distinguishes complete enumerator reports, candidate limits,
wall-time limits, cancellation, and errors. Even a complete report remains
unverified. Canonical mathematical objects retain ordinary artifact identity;
the search key separately hashes the canonical object digest together with the
canonicalizer implementation digest.

Representation changes follow a proposer/checker split. A transformer stores
the target, relation label, implementation digest, and proof obligation.
`transform.verify` rebinds both source and target schemas, semantics, and
digests before dispatching to an operator-authorized checker.

The initial `polytope.separate` backend covers finite rational V-represented
polytopes. Z3 proposes exact convex weights or an exact separator. Independent
checkers replay those objects using `Fraction` arithmetic and do not import
Z3.

## Resumable strategy search

The provisional M3 service keeps coordination deliberately local:

```text
idempotent request
    → SQLite acceptance row + append-only event
    → proposer/evaluator/oracle/refiner child processes
    → immutable archive page + checkpoint
    → atomic snapshot update
    → pause, resume, or terminal archive
```

An idempotency key binds one exact request digest to one experiment URI.
Concurrent submissions of that request reuse the accepted experiment; the same
key cannot be rebound to another request. Plugin work performed after the last
checkpoint may run again after process loss, but only committed pages and
checkpoints become durable lineage.

On startup, active experiments are changed to `PAUSED`, while pending
cancellation becomes `CANCELLED`. A malformed snapshot is moved to `ERROR` and
recorded in `search_recovery_failures` without preventing unrelated rows from
recovering. Checkpoint restoration rebinds the request, plugin snapshot,
implementation digests, effective budget, environment, archive pages, and
accounting before opaque strategy state is accepted.

The reference scheduler accepts one strategy worker and requires one active
Jacobian process per state directory. SQLite provides transactional request
acceptance, not a distributed worker lease.

## Conjecture transformations and parameter regions

The three hypothesis-producing M4 operations share an untrusted
`HypothesisTransformer`. The service validates source evidence, stores each
claim and edit as immutable artifacts, deduplicates by content identity, and
may route a hypothesis through M3 falsification. Generated, repaired, and
generalized statements remain `UNVERIFIED`.

A parameter-region plugin may return `PROPOSED` or `SAMPLED` evidence only.
Jacobian commits an immutable `ParameterRegionSubject` binding the target claim,
region kind, exact conditions, and sample artifacts. Promotion requires an
authorized certificate record whose exact claim and subject artifact URIs are
parents of that record. The service replays the certificate and accepts the
promotion only if replay reproduces the same verification-record URI.
Mathematical interpretation of the region remains in the authorized checker;
the generic kernel only enforces bindings and evidence state.

## MCP boundary

The engine is a normal Python library and CLI. MCP is a thin adapter:

- Tools perform bounded computations or state changes.
- Resources expose large artifacts, traces, and experiment state.
- Tool responses contain only compact structured summaries and resource URIs.
- Long-running searches return an experiment handle.
- Scope and archive artifacts are immutable; the experiment snapshot is a
  durable lifecycle record.

The engine does not expose a generic public `solver.solve`. Solver families have
different inputs, guarantees, and certificates, and remain typed internal
backends.
