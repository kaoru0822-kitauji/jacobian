# Reference benchmarks

[Documentation home](../index.md)

Benchmarks validate the generic runtime; they do not define its public API.

This document defines pass/fail mathematical workloads. Operational speed and
resource measurements are specified in
[Performance benchmarks](performance-benchmarks.md), and model behavior is
evaluated separately in [Agent evaluations](agent-evaluations.md).

The exact component fixtures and their public oracles are specified in the
[Mathematical scenario catalog](math-scenarios.md).

The committed
[Harbor regression-v1 dataset](../../benchmarks/regression-v1/README.md)
contains twenty-two bounded, offline mathematical workflow tasks. Its task digests,
clean-room verifiers, and Oracle job are the canonical validation surface.

The full on-disk ownership map lives in
[`benchmarks/README.md`](../../benchmarks/README.md): Harbor datasets,
research challenges, public reproductions, performance microbenchmarks, and
provider spikes are separate classes.

The 18 public research challenges remain candidate material under
`benchmarks/research/challenges/`; they are not source-oriented dataset splits
and are not silently promoted into regression-v1.

## Benchmark hierarchy

Jacobian distinguishes:

1. contract and adversarial conformance cases;
2. small public mathematical scenarios;
3. domain capability workflows;
4. held-out structural variants for models;
5. historical end-to-end research episodes.

A famous conjecture is not a substitute for the first three layers. It is too
difficult to diagnose and too easy to contaminate through public solutions.

## Cross-domain coverage

A single domain can accidentally bake its own assumptions into apparently
generic interfaces. The benchmark portfolio therefore includes structurally
different domains and representations. This is evidence about runtime
generality and agent composition, not a gate on which experimental
capabilities may be installed.

## Reference A: finite directed graphs and path languages

The graph benchmark family uses tiny directed graphs to test:

- complete semantic closure rather than intended path lists;
- structured path and odd-cycle witnesses;
- graph candidate validation;
- candidate and witness shrinking;
- finite enumeration certificates.

`PATH-CLOSURE-001` and `GRAPH-BIP-001` are the initial public cases. Their
checker implementation does not import the graph search implementation.

## Reference B: bounded integer matrices

The matrix benchmark family uses integer-matrix candidates, kernel-vector
witnesses, and finite determinant certificates. `MAT-KERNEL-001` and
`MAT-MAXDET3-001` are the initial public cases.

It should test that the runtime does not assume:

- candidates are graphs;
- semantic closure means path enumeration;
- canonicalization is always graph isomorphism;
- every search uses mutation;
- witnesses have the same representation as candidates.

## Reference C: bounded Erdős-Straus decompositions

The Erdős-Straus benchmark family verifies finite intervals of the
unit-fraction statement. `ERDOS-STRAUS-001` binds the interval, a complete
decomposition table, and exact integer replay. Its checker is independent of
the table-generation routine. The case tests positive exhaustive witnesses and
the requirement that a bounded result not be generalized to the open
conjecture.

## Finite magmas

`MAGMA-IMPL-001` adds finite operation tables, equational-law evaluation, and a
model-plus-assignment witness. It broadens the portfolio beyond graphs and
linear algebra and can be enabled whenever its capability and oracle are ready.

## Historical end-to-end episodes

The Dinitz–Garg–Goemans routing episode remains a valuable regression
because it combines semantic closure, adversarial routing, rational arithmetic,
polyhedral separation, and shrinking. It tests whether an agent can compose
several operations while preserving artifacts and verification boundaries.

Add historical conjecture episodes with temporal knowledge cutoffs as their
inputs and independent oracles become available. A corpus provider used in
these evaluations must not retrieve information published after a benchmark's
cutoff date.

Public known answers are suitable for conformance and regression. Held-out
model evaluation uses generated structural variants with separate hidden
oracles.
