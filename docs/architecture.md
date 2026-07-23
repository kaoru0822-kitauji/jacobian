# Architecture

## Purpose

Jacobian separates mathematical discovery from mathematical trust.

Models, search algorithms, and domain solvers are allowed to be heuristic,
stochastic, incomplete, and frequently replaced. Verification is performed by
small, operator-authorized checkers against versioned formal claims and domain
semantics.

The durable product is the replayable verification contract:

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
- Model-uploaded code introduced in later releases

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

### Run record

Execution metadata such as runtime, seed, environment, limits, logs, and tool
version. A run record does not change the identity of the mathematical object.
v0.1 persists verification records; generic experiment-run persistence begins
with the bounded-discovery job model in v0.2.

### Knowledge record

A curated record promoted from experiments after deduplication and review.
Raw runs never become trusted knowledge merely because they were stored.

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
```

Search plugins cannot register themselves as trusted checkers. The checker
registry is operator-managed and binds checker digests to supported claim,
semantics, and certificate versions.

## Search and checker separation

The independent checker may share stable wire schemas and primitive exact
arithmetic types with the search side. It must not import the search evaluator,
oracle, canonicalizer, or solver integration.

Higher assurance may add a second implementation using a different algorithm or
a proof-assistant kernel. Different programming languages are useful for
defense in depth, but language diversity alone does not establish mathematical
independence.

## MCP boundary

The engine is a normal Python library and CLI. MCP is a thin adapter:

- Tools perform bounded computations or state changes.
- Resources expose large artifacts, traces, and experiment state.
- Tool responses contain only compact structured summaries and resource URIs.
- Long-running searches return an experiment handle.
- Immutable experiment snapshots are content-addressed artifacts.

The engine does not expose a generic public `solver.solve`. Solver families have
different inputs, guarantees, and certificates, and remain typed internal
backends.
