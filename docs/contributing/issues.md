# Issue index

[Documentation home](../index.md)

GitHub is the source of truth for implementation issues. This file records the
small amount of repository context that should remain stable across issue
updates; it does not duplicate full issue bodies.

## Foundational issues

The original verification-runtime decisions and implementation work were posted
as:

| Area | GitHub issue |
| --- | --- |
| Verification-kernel contract | [#1](https://github.com/morluto/jacobian/issues/1) |
| Artifact, claim, evidence, and result contracts | [#2](https://github.com/morluto/jacobian/issues/2) |
| Artifact identity and storage | [#3](https://github.com/morluto/jacobian/issues/3) |
| Plugin manifests and capabilities | [#4](https://github.com/morluto/jacobian/issues/4) |
| Checker registry and authorization | [#5](https://github.com/morluto/jacobian/issues/5) |
| Witness and certificate verification | [#6](https://github.com/morluto/jacobian/issues/6) |

Their descriptions reflect the repository state when filed. The current
normative behavior is defined by the
[v0.2 specification](../reference/specifications/v0.2.md) and
[v0.2 conformance suite](../reference/conformance-v0.2.md).

## Current implementation

The repository implements the verification runtime together with:

- bounded enumeration experiments and cancellation;
- implementation-bound canonicalization;
- transformation proposal and independent verification;
- exact finite rational convex-hull membership and separation;
- CLI and MCP adapters;
- explicit domain bundles for arithmetic, number theory, combinatorics, finite
  sets, sequences, geometry, graph optimization and invariants, matrices,
  lattices, polynomials, projective geometry, universal algebra, validated
  analysis, finite probability, and rational optimization; and
- typed Lean proof states, premise retrieval, dependency subgraphs, proof-edit
  validation, and independent proof replay.

Do not open umbrella issues that merely restate the product goals.

## Follow-up issue policy

Open a new issue when review, conformance testing, or real use identifies a
specific unresolved behavior. Each issue should:

- describe the observable mathematical or operational problem;
- distinguish verified facts from hypotheses;
- name the affected public contract or conformance case;
- include a minimal reproduction or failing test where practical;
- state whether the change can affect artifact identity, checker authority,
  evidence binding, or experiment integrity;
- avoid prescribing a solver or backend unless the requirement depends on it.

Product goals should become issues only when the mathematical or operational
problem and success criteria are concrete. The active direction remains in the
[product goals](../explanation/goals.md).
