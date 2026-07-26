---
name: implement-math-capability
description: Implement an evidence-backed mathematical capability in Jacobian from an accepted discovery candidate or concrete capability specification. Use when asked to add, prototype, scaffold, or extend a domain-owned capability; turn a mathematical operation into bounded Pydantic contracts, adapters, artifacts, catalog registration, failure semantics, and reproduction tests; or repair an implementation whose atomicity, completeness, provenance, or assurance is unclear. Use discover-math-capabilities first when the question is what to build, implement-math-capability-checker for an independent verification path, and evaluate-math-capabilities for comparative portfolio value.
---

# Implement Math Capability

Turn one accepted mathematical outcome into an experimental Jacobian
capability. Optimize routine mechanics without weakening mathematical,
artifact, or trust boundaries.

## Confirm the implementation handoff

Require a concrete candidate or specification that states:

- the single agent-visible mathematical outcome;
- supporting move episodes or the fundamental-primitive exception;
- current catalog overlap and why composition does not already suffice;
- typed inputs, output, useful intermediate artifacts, and downstream use;
- domain semantics, exactness, determinism, scope, and completeness;
- maintained backend, version constraints, and license;
- failure and inapplicability conditions;
- attainable assurance and any independent-checking obligation;
- one public reproduction and one plausible false or incomplete path; and
- the later evaluation hypothesis.

Return an unclear product question to `discover-math-capabilities`. Do not
invent recurrence or leverage from a backend API.

## Inspect local ownership and precedent

Read `AGENTS.md`, `CONTRIBUTING.md`, and the relevant product and tool
references. Inspect `capability://catalog`, nearby descriptors, contracts,
artifacts, adapters, checkers, tests, and kernel registration.

Choose an existing domain owner and artifact type where possible. Add a new
capability ID only when it exposes a distinct mathematical outcome. Extend an
existing batch when the new result has the same inputs, semantics, execution
boundary, and artifact ownership without hiding per-result status.

Prefer a thin adapter to a maintained system. Verify current APIs against
official documentation and source. Pin the distribution and effective
mathematical backend when reproducibility, certificates, or compatibility
depend on them.

## Freeze the contract before computation

Define the complete request model and cross-field invariants before invoking
the backend or writing operation artifacts. Bound every dimension that can
drive time, memory, enumeration, expression growth, or output size.

Use domain-owned schemas. Include only fields needed to determine the
mathematical outcome. Avoid arbitrary expression strings, backend command
bags, boolean mode soup, and generic object/value contracts.

Define a closed result model that separates:

- execution status;
- input validity;
- mathematical conclusion, if any;
- exactness and determinism;
- declared scope and parameters;
- completeness and its basis;
- assurance and its basis;
- candidate, witness, certificate, and checker availability; and
- backend identity and version.

Specify normalization and canonicalization wherever equivalent answers exist.
If no stable canonical form is justified, expose the chosen convention rather
than implying uniqueness.

## Select the capability shape

Use the narrowest fitting shape:

- **Exact computation:** return one complete value or object for bounded input.
- **Predicate decision:** return a boolean only when every valid input is
  decidable under the declared scope.
- **Transformation or normal form:** preserve the source, transformed object,
  convention, and replay relation.
- **Bounded enumeration:** expose items, coverage, truncation, and a durable
  enumeration artifact.
- **Witness-producing search:** keep incumbent/witness, search scope, and
  optimality or exhaustion obligations separate.
- **Certificate-producing computation:** preserve the candidate and
  certificate but stop below `VERIFIED`.
- **Optional backend:** advertise runtime availability and fail before
  execution when the pinned provider is unavailable.

One adapter may coordinate backend calls for one outcome. Do not move
multi-step mathematical strategy into the kernel.

## Implement the boundary

Follow the local adapter pattern:

1. Validate the full Pydantic request.
2. Check mathematical preconditions that can fail cheaply.
3. Invoke the backend inside the narrow expected exception boundary.
4. Construct and validate the mathematical result in memory.
5. Materialize the validated input artifact.
6. Materialize result and useful intermediate artifacts with parent links.
7. Return a result envelope whose relationships bind exact artifact URIs.
8. Register the adapter through the existing kernel/catalog path.

Do not write operation artifacts before validation and computation can
successfully produce a contract-valid result. If preserving a failed attempt
is useful, use an explicit episode or diagnostic artifact contract rather than
leaving half of a success artifact graph.

Use capability-specific diagnostic codes and actionable stages. Keep these as
non-conclusions:

- invalid or inapplicable input;
- unavailable backend;
- timeout or cancellation;
- backend or protocol error;
- incomplete enumeration;
- failure to find a witness; and
- failure to construct or validate a certificate.

## Assign assurance honestly

A deterministic exact backend can support `COMPUTED`; it does not independently
verify itself. Search, generation, evaluation scores, solver statuses, and
producer-side reconstruction never directly support `VERIFIED`.

If verification is justified, preserve the candidate and its open obligations,
then hand the independent path to `implement-math-capability-checker`. Do not
import checker authorization into the producer or plugin.

## Add proportionate proof

At minimum add:

- descriptor, schema, and catalog uniqueness/installation coverage;
- one representative completing reproduction;
- exact inline output and persisted artifact assertions;
- artifact parent and relationship assertions;
- one boundary-value case;
- one invalid or mathematically inapplicable case proving fail-closed behavior
  and absence of success artifacts; and
- timeout, cancellation, unavailable-runtime, incomplete-search, or malformed
  backend cases when the capability can reach them.

For a family, invoke every ID through the public registry but test semantics by
meaningful equivalence classes rather than mirroring every implementation
branch. Public motivating cases are regressions, not held-out evidence of
portfolio value.

When feasible, show that a regression test fails on the base for the intended
missing behavior. Do not assert private helper names or copied source text.

## Keep experimental work fast

For a new experimental capability, require contract honesty, boundedness,
artifacts, fail-closed behavior, and focused reproductions. Do not require an
independent checker or comparative evaluation merely to make the experiment
available.

Avoid premature compatibility layers, generalized factories, speculative
configuration, exhaustive documentation, and one adapter class per
declarative primitive when a typed local registry is clearer. Reuse a small
capability-definition helper only after repeated adapters reveal the same
stable variation points.

Stabilization, recommendation, default ranking, consolidation, and retirement
require stronger evaluation and compatibility evidence.

## Validate and hand off

Run focused tests while implementing, then the repository-prescribed check for
the exact final tree. Report only validation that ran and any unavailable
runtime or proof gap.

Produce an implementation handoff containing:

- capability IDs and versions;
- source candidate and outcome;
- contracts, semantics, artifacts, and relationships;
- provider identity and resource bounds;
- every failure/non-conclusion state;
- attainable assurance and open checker obligations;
- public reproductions and validation evidence;
- compatibility status; and
- the exact control/treatment delta for `evaluate-math-capabilities`.

Use `implement-math-capability-checker` only for a separately justified
verification path. Use `evaluate-math-capabilities` to decide whether the
experimental addition should be kept, expanded, split, consolidated,
recommended, stabilized, or retired.

## Reject these implementations

Do not ship:

- one ID per library function without workflow evidence;
- generic CAS, Python, shell, solver, or proof-assistant execution;
- opaque `solve`, `research`, or `prove` workflows;
- unbounded enumeration presented as complete;
- an incumbent presented as an optimum;
- empty search presented as nonexistence;
- approximate output presented as exact;
- producer replay presented as independent verification; or
- a result envelope that merges execution, conclusion, completeness, and
  assurance.
