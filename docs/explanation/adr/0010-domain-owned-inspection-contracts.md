# ADR 0010: Domain-owned inspection contracts

- Status: Accepted
- Date: 2026-08-01

## Context

Jacobian exposes mathematical outcomes as small, composable capabilities. A
single proof representation shared by every domain would make syntax, typing,
trust, and completeness decisions implicit in a generic contract. It would
also encourage inspection output to be mistaken for independently checked
evidence.

The current claim-decomposition contract is intentionally narrower: it records
bounded propositional structure, ordered conjunction and implication children,
source spans, opaque atom bindings, and deterministic reconstruction evidence.
That scope is useful for its producer and does not define a general proof
language.

## Decision

Jacobian does not provide a universal cross-domain proof AST. A versioned
domain-owned intermediate representation is appropriate only when a concrete
producer, transformation, or checker needs that representation to expose one
bounded outcome. Each such contract must state its supported syntax, parser
uncertainty, unsupported forms, identity bindings, and completeness semantics.

Inspection artifacts are computed facts and never verification evidence. They
cannot authorize a checker, change trust policy, or emit `VERIFIED`.

Quantifiers, parameter dependencies, typed inference, and asymptotic
uniformity are separate mathematical outcomes. They require their own
evidence-backed capability discovery rather than being smuggled into a shared
proof representation.

## Consequences

Existing domain contracts remain the authority for their own outcomes. The
bounded propositional claim decomposition remains available, while speculative
duplicate proof and Lean artifact contracts are removed. New formal inspection
or transformation work must name its domain, exact scope, and independent
assurance boundary before a contract is added.
