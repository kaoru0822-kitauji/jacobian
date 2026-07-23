# Reference benchmarks

Benchmarks validate the generic kernel; they do not define its public API.

## Why more than one benchmark is required

A single domain can accidentally bake its own assumptions into apparently
generic interfaces. Jacobian therefore does not stabilize the v0.1 capability
interfaces until at least two structurally different plugins use them.

## Benchmark A: bounded routing counterexample

The Dinitz–Garg–Goemans episode is a strong adversarial benchmark because it
requires:

- pure-data graph and rational-flow candidates;
- complete semantic closure rather than intended path lists;
- structured hidden-path and routing witnesses;
- exact capacity and cost replay;
- candidate and witness shrinking;
- finite enumeration certificates.

The benchmark should include both false restricted-path candidates and the
small verified counterexample. It tests whether omitted legal objects can cause
a false discovery.

The DGG schemas, paths, and checker implementation live in a domain plugin and
benchmark package. They are not part of the generic kernel specification.

## Benchmark B: bounded binary-matrix problem

The second plugin should use matrix candidates and a different witness shape,
for example a bounded discrepancy, determinant, or forbidden-submatrix
property.

It should test that the kernel does not assume:

- candidates are graphs;
- semantic closure means path enumeration;
- canonicalization is always graph isomorphism;
- every search uses mutation;
- witnesses have the same representation as candidates.

The exact benchmark statement should be selected before implementation based on
the availability of a small independent checker and useful failure witnesses.

## Historical benchmarks after v0.4

Later evaluation should add historical conjecture episodes with temporal
knowledge cutoffs. The system must not retrieve information published after the
benchmark's cutoff date.
