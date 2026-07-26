---
name: implement-math-capability-checker
description: Design and implement an operator-authorized independent checker for a Jacobian mathematical capability, witness, certificate, transformation, normal form, optimum, or exact relation. Use when asked to move a capability beyond COMPUTED, define proof obligations or certificate formats, add verification replay, audit checker independence, harden artifact and semantic binding, or add adversarial false-certification tests. Use implement-math-capability for the producer and evaluate-math-capabilities to measure whether verification improves agent outcomes.
---

# Implement Math Capability Checker

Build a verification path whose authority, implementation, and evidence are
independent of the producer, search, or evaluator it checks.

## Confirm checker-worthiness

Start from a stable candidate artifact and exact relation. Require:

- the capability and producer contract;
- the precise claim eligible for verification;
- all mathematical obligations needed for that claim;
- the exact semantics, normalization, scope, and completeness convention;
- a candidate or certificate format;
- a plausible implementation independent of the producer;
- a reason stronger assurance changes downstream agent behavior; and
- attack cases that could fool superficial replay.

Return producer-contract gaps to `implement-math-capability`. Return unclear
mathematical outcomes to `discover-math-capabilities`. Do not add a checker
only to increase assurance labels.

## Write the obligation ledger

Before code, enumerate every necessary obligation:

| Obligation | Bound input | Checked evidence | Rejection condition | Checker method |
| --- | --- | --- | --- | --- |

Include structural, algebraic, semantic, scope, completeness, normalization,
and provenance obligations. Distinguish:

- candidate or witness feasibility;
- reconstruction or relation correctness;
- canonical-form conditions;
- independence, spanning, minimality, maximality, or optimality;
- enumeration exhaustion;
- statement/environment identity; and
- certificate integrity.

Checking a feasible witness does not verify optimality. Checking a numerical
field does not verify the surrounding theorem. Checking a proof of a nearby
statement does not verify the requested claim.

If no bounded checker can discharge every obligation, narrow the verifiable
claim or preserve an explicit open obligation.

## Establish independence

Trace dependencies for producer and checker. The checker must not depend on:

- the producer's search or proposal implementation;
- producer-derived cached results;
- a shared helper that embodies the relation being checked;
- the same solver status or opaque backend answer;
- evaluator scores or model judgments; or
- plugin-selected executable code or trust policy.

Shared codecs and passive domain types may be acceptable when they do not
decide the mathematical relation. Shared parsing still requires malformed and
semantic-mismatch attack tests.

Choose one:

- a small independently written exact replay;
- a separately maintained and pinned backend;
- a proof-assistant kernel check;
- a certificate verifier substantially simpler than certificate search; or
- two independent obligations whose conjunction proves the declared claim.

Document the independence argument and its limitations. Different capability
IDs around the same function are not independence.

## Bind the certificate and verification request

Define a versioned certificate or witness artifact containing only durable,
typed evidence. Bind verification to:

- exact claim or relation identity;
- domain semantics and supported versions;
- source/input artifact digests;
- candidate artifact and payload digest;
- scope, bounds, normalization, and completeness convention;
- certificate format and version;
- producer identity where relevant;
- checker identity, version, executable digest, and configuration; and
- environment/toolchain identity for formal artifacts.

Reject substitution of isomorphic, reordered, normalized differently, or
otherwise equivalent objects unless the verified relation explicitly permits
that equivalence and the certificate proves the binding.

The request may select a registered certificate format; it may not supply or
authorize executable checker code.

## Keep authorization outside mathematics

Register checker authority through the operator-managed checker registry.
Plugins, producers, search workers, evaluation harnesses, and callers cannot:

- authorize a checker;
- expand supported claim or semantics versions;
- override revocation;
- change trust policy; or
- construct a verified record directly.

Separate availability, recommendation, compatibility, and authorization.
An available checker need not be recommended; a compatible checker need not be
authorized.

## Implement fail-closed replay

Validate the complete verification request and resolve all bound artifacts
before mathematical checking. Run the checker within declared resource and
environment limits.

Return distinct outcomes for:

- verified relation;
- rejected candidate or certificate;
- invalid verification request;
- unsupported semantics or certificate version;
- unauthorized or revoked checker;
- missing or mismatched artifact;
- unavailable checker runtime;
- timeout;
- cancellation; and
- checker/protocol error.

Only the verified path may originate `VERIFIED`. Rejection means the submitted
evidence failed; it is not automatically the negation of the mathematical
claim. Timeout, cancellation, error, or missing evidence are always
non-conclusions.

Write verification records only after the checker has produced and the kernel
has validated a complete result. Bind the record to every checked artifact and
checker identity.

## Attack the trust boundary

Add tests for the valid certificate and, as applicable:

- candidate artifact substitution;
- source artifact substitution;
- correct payload under the wrong semantics;
- wrong scope, bound, variable order, normalization, or environment;
- partial certificates that satisfy reconstruction but not completeness;
- feasible but nonoptimal witnesses;
- linearly dependent, nonspanning, or noncanonical bases;
- altered statements with reusable proofs;
- producer/checker shared-dependency regressions;
- forged checker identity or executable digest;
- unregistered, unauthorized, incompatible, and revoked checkers;
- malformed evidence and protocol output;
- unavailable runtime, timeout, and cancellation; and
- attempts to deserialize failures as false, infeasible, exhaustive, or
  verified conclusions.

For each negative test, state which obligation it attacks. Prefer one mutation
per case so failures remain diagnostic.

## Validate independence and behavior

Inspect the complete producer/checker dependency graph and exact diff. Run:

- contract and malformed-input tests;
- checker unit tests;
- integration replay through public capability dispatch;
- authorization and revocation tests;
- timeout/cancellation/runtime tests;
- the repository-prescribed final validation; and
- an independent exact-diff review when required by repository risk policy.

Where feasible, demonstrate that attack tests fail against an intentionally
weakened checker or the pre-fix base for the intended reason. Never weaken the
oracle or test merely to make the checker pass.

## Hand off to evaluation

Return:

- the exact verifiable claim;
- obligation ledger and discharged obligations;
- certificate/witness format and artifact bindings;
- producer and checker dependency comparison;
- registry authorization and compatibility scope;
- all non-verifying outcomes;
- attack-test evidence;
- runtime and operational limits;
- residual proof gaps; and
- a treatment definition that adds verification without changing the producer
  outcome.

Use `evaluate-math-capabilities` to measure false certification, false
rejection, downstream use of verified evidence, discovery cost, calls, tokens,
and runtime relative to leaving the result at `COMPUTED`.

## Reject these checker designs

Do not accept:

- producer self-replay labeled independent;
- a second wrapper around the same opaque solver answer;
- verification of only the easiest field of a stronger result;
- implicit semantics or normalization;
- caller- or plugin-authorized executable code;
- a checker that turns failure into mathematical negation;
- `VERIFIED` evidence unbound from exact artifacts and scope; or
- a certificate more complex and less inspectable than the original search
  without a clear trust advantage.
