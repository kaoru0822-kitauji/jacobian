# v0.1 conformance specification

## Purpose

The conformance suite determines whether an implementation satisfies the v0.1
verification contract. It runs against at least two structurally different
reference plugins.

Passing a happy-path benchmark is insufficient. Every integrity attack below
must fail closed.

The suite is one part of the broader [testing strategy](testing-strategy.md).
Conformance is a correctness gate and is never replaced by code coverage,
performance results, or successful model-in-the-loop evaluations.

## Artifact identity

| ID | Test | Required result |
| --- | --- | --- |
| ART-001 | Insert the same canonical object twice | Same object digest; idempotent insertion |
| ART-002 | Encode equivalent reduced rationals | Same canonical object digest |
| ART-003 | Reuse identical payload bytes under another schema | Different object identity |
| ART-004 | Reuse identical payload bytes under another semantics digest | Different object identity |
| ART-005 | Modify a stored blob | Digest verification failure |
| ART-006 | Insert duplicate JSON keys or a disallowed float | Input rejected |
| ART-007 | Exceed artifact size or nesting limits | Bounded rejection without partial commit |

## Operational and mathematical state

| ID | Test | Required result |
| --- | --- | --- |
| RES-001 | Evaluator times out | `execution = TIMEOUT`; no false conclusion |
| RES-002 | Evaluator crashes | `execution = ERROR`; no verified record |
| RES-003 | Enumeration reaches a declared limit | Coverage is not exhaustive |
| RES-004 | Floating evaluation reports a positive margin | Result remains unverified |
| RES-005 | Exact evaluator claims exhaustive coverage without checked evidence | Result remains unverified |

## Witness verification

| ID | Test | Required result |
| --- | --- | --- |
| WIT-001 | Verify a valid direct witness | Verified logical effect |
| WIT-002 | Reference an object outside the witness domain | Witness rejected |
| WIT-003 | Bind a valid witness to another candidate | Binding rejected |
| WIT-004 | Mutate one witness component | Replayed result changes or fails |
| WIT-005 | Oracle returns a witness after timeout metadata | Witness is judged only by independent replay |

## Certificate verification

| ID | Test | Required result |
| --- | --- | --- |
| CRT-001 | Replay a valid finite enumeration certificate | Verified conclusion |
| CRT-002 | Copy the certificate to another claim | Binding rejected |
| CRT-003 | Change its semantics, scope, candidate, or encoding digest | Binding rejected |
| CRT-004 | Request an unregistered checker | Result remains unverified |
| CRT-005 | Use a revoked checker for new verification | Verification denied by policy |
| CRT-006 | Corrupt the certificate payload | Verification failure |
| CRT-007 | Return `NONE_CERTIFIED` without a verified certificate record | Protocol violation |

## Plugin isolation

| ID | Test | Required result |
| --- | --- | --- |
| PLG-001 | Plugin manifest declares a trusted checker | Declaration ignored or rejected |
| PLG-002 | Plugin omits a required capability | Failure before execution |
| PLG-003 | Plugin changes semantics without changing its digest | Manifest or digest validation failure |
| PLG-004 | Verification package imports search implementation | Dependency-boundary test failure |
| PLG-005 | Two domains expose different optional capabilities | Core tools remain usable in both |

## Shrinking

| ID | Test | Required result |
| --- | --- | --- |
| SHR-001 | Reducer proposes a smaller preserving target | Accepted after checker replay |
| SHR-002 | Reducer breaks the predicate | Rejected |
| SHR-003 | Budget ends before checked neighborhood exhaustion | Honest minimality class |
| SHR-004 | Tool claims global minimality without certificate | Protocol violation |
| SHR-005 | Final target lacks a fresh verification record | Output remains unverified |

## Record and replay

| ID | Test | Required result |
| --- | --- | --- |
| RPL-001 | Inspect a verification record | Exact checker and environment digests are present |
| RPL-002 | Change authorized checker bytes before replay | New verification is denied |
| RPL-003 | Replay a completed bundle in a clean process | Same verified conclusion |
| RPL-004 | Replay with a missing dependency artifact | Explicit resolution failure |
| RPL-005 | Revoke a checker while verification is in flight | No record commits after revocation completes |
| RPL-006 | Present schema-invalid data under an authorized schema URI | Verification is rejected before checker dispatch |

Generic evaluation caching is deferred beyond v0.1. When introduced, changing
an evaluator, checker, scope, limit, or semantics-relevant environment field
must produce a cache miss.

## Cross-domain gate

The reference plugins must differ in candidate representation, witness shape,
and optional capabilities.

The suite passes only when:

- both plugins use the same generic core schemas and tools;
- no domain-specific type is added to the kernel to make either plugin pass;
- all required tests succeed;
- any unsupported optional capability is reported explicitly;
- every verified result identifies the exact checker digest used.
