# Reference benchmarks

[Documentation home](../index.md)

Benchmarks validate the generic kernel; they do not define its public API.

This document defines pass/fail mathematical workloads. Operational speed and
resource measurements are specified in
[Performance benchmarks](performance-benchmarks.md), and model behavior is
evaluated separately in [Agent evaluations](agent-evaluations.md).

The exact component fixtures and their public oracles are specified in the
[Mathematical scenario catalog](math-scenarios.md).

## Benchmark hierarchy

Jacobian distinguishes:

1. contract and adversarial conformance cases;
2. small public mathematical scenarios;
3. reference-plugin workflows;
4. held-out structural variants for models;
5. historical end-to-end research episodes.

A famous conjecture is not a substitute for the first three layers. It is too
difficult to diagnose and too easy to contaminate through public solutions.

## Why more than one reference plugin is required

A single domain can accidentally bake its own assumptions into apparently
generic interfaces. Jacobian therefore does not stabilize the v0.2 capability
interfaces until at least two structurally different plugins use them.

## Reference A: finite directed graphs and path languages

The first plugin uses tiny directed graphs to test:

- complete semantic closure rather than intended path lists;
- structured path and odd-cycle witnesses;
- graph candidate validation;
- candidate and witness shrinking;
- finite enumeration certificates.

`PATH-CLOSURE-001` and `GRAPH-BIP-001` are the initial public cases. Their
checker implementation does not import the search plugin's graph routines.

## Reference B: bounded integer matrices

The second plugin uses integer-matrix candidates, kernel-vector witnesses, and
finite determinant certificates. `MAT-KERNEL-001` and `MAT-MAXDET3-001` are the
initial public cases.

It should test that the kernel does not assume:

- candidates are graphs;
- semantic closure means path enumeration;
- canonicalization is always graph isomorphism;
- every search uses mutation;
- witnesses have the same representation as candidates.

## Third-domain candidate: finite magmas

`MAGMA-IMPL-001` adds finite operation tables, equational-law evaluation, and a
model-plus-assignment witness. It is the preferred third plugin after the v0.2
capability surface is stable.

## Historical end-to-end episodes

The Dinitz–Garg–Goemans routing episode remains a valuable later regression
because it combines semantic closure, adversarial routing, rational arithmetic,
polyhedral separation, and shrinking. It is not the definition of v0.2 and does
not block the first verification kernel.

After M5, add historical conjecture episodes with temporal knowledge cutoffs.
The optional corpus provider must not retrieve information published after a
benchmark's cutoff date.

Public known answers are suitable for conformance and regression. Held-out
model evaluation uses generated structural variants with separate hidden
oracles.
