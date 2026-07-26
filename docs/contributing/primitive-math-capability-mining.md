# Primitive mathematics capability mining

[Documentation home](../index.md)

- Status: Experimental portfolio research record
- Research snapshot: 2026-07-26
- Baseline: `main` at `11cb9d7d149c4c27c297409cfc47d2a646c033ec`
- Source index: Google Sheets tab `gid=1899476594`, 707 data rows

## Decision

Expose 108 bounded, exact primitive outcomes across integer arithmetic, modular
arithmetic, elementary combinatorics, exact rationals, finite integer sets, and
finite integer sequences. They are experimental `EXPLORE` capabilities behind
`capability.invoke`, not new top-level MCP tools.

The adapters preserve the exact input and result as content-addressed
artifacts. They report deterministic full coverage of the supplied bounded
input at `COMPUTED` assurance. They do not report `VERIFIED`: the same pinned
SymPy runtime supplies the result and therefore cannot independently certify
it.

This is a breadth experiment, not evidence that all 108 IDs improve autonomous
agent performance. The public cases below establish contract fit. Portfolio
value, discovery cost, and consolidation belong in held-out ablations.

## Source bundle

The spreadsheet was exported as CSV rather than copied into the repository.
It is an index, not a mathematical authority. Its rows include 70 GitHub
repositories, 64 Erdős problem pages, 47 Hugging Face datasets, 29 research
papers, 27 mirrored CodeCube tasks, 23 mathematician blog posts, and smaller
formal-library, forum, and benchmark groups. Six rows omit a domain and several
rows contain only title-level metadata.

A bounded URL census covered all 706 unique URLs. It retrieved 431 with HTTP
200 and 239 with HTTP 206; 36 returned an access error, rate limit, missing
page, or connection failure. Those 36 remain unknown rather than negative
evidence. The temporary census records redirects, content types, titles, and
errors; it is not committed because it is a dated URL inventory rather than a
stable mathematical artifact.

The following primary slices informed this batch:

| Source | Pinned identity and constraints | Process evidence used |
| --- | --- | --- |
| [Erdős Problems 124](https://www.erdosproblems.com/124), [205](https://www.erdosproblems.com/205), [370](https://www.erdosproblems.com/370), [401](https://www.erdosproblems.com/401), [707](https://www.erdosproblems.com/707), and [1202](https://www.erdosproblems.com/1202) | Pages inspected 2026-07-26; community-curated statements and status, with linked formal artifacts where present | Base expansion, prime factor multiplicity, prime factors, factorial divisibility, finite-set containment/differences, congruence classes, and exact integer inequalities recur as useful intermediate moves |
| Formal Conjectures [PR 4542](https://github.com/google-deepmind/formal-conjectures/pull/4542) and issues [4133](https://github.com/google-deepmind/formal-conjectures/issues/4133), [1347](https://github.com/google-deepmind/formal-conjectures/issues/1347), [1137](https://github.com/google-deepmind/formal-conjectures/issues/1137), [4493](https://github.com/google-deepmind/formal-conjectures/issues/4493), and [4590](https://github.com/google-deepmind/formal-conjectures/issues/4590) | Exact thread bodies synchronized 2026-07-26; linked Lean commits remain the stronger evidence | Exact cardinalities, degree sequences, averages, ceilings, set witnesses, factor/congruence boundaries, and quantifier/domain corrections alter proof and counterexample decisions |
| `nvidia/Nemotron-Math-Proofs-v2` | revision `7665d7f1d006fd89aa852a9dab8060c60b63f814`; CC-BY-4.0 | Rows separate problems, proposed proofs, verification, and meta-verification. Elementary exact calculations remain visible inside proof episodes |
| `ufal/leantree` | revision `ea65c26187a456958f17d57b28376aec1dedf1a7`; CC-BY-4.0 | Proof-tree rows expose goal states, hypotheses, tactic transitions, dependencies, proof depth, and proof size |
| `uw-math-ai/theorem-search-dataset` | revision `c24670fc19563640c7c15182ecb493ad2a4f2a9e`; CC-BY-SA-4.0 | Theorem rows expose stable statement identifiers, bodies, labels, sources, and parsing methods |
| `uw-math-ai/math-graph` | revision `ced4ca9de1bd9e5b67aa09d1d515e270e438fa1e`; CC-BY-4.0 | Formal-dependency rows preserve source, dependency, edge type, binder, role, and position |
| `INSAIT-Institute/BrokenMath` | revision `5eda8c5fbd150afde41b6206b60700ab7d8e25c7`; CC-BY-NC-SA-4.0 | Adversarial rows show that a changed predicate can invalidate an otherwise applicable numerical solution |
| `leanpolish-anon/lean-proof-compression` | revision `e161aae6770178bf96fd6dd0eecc4715106ec7fd`; Apache-2.0 | Accepted and rejected proof edits preserve exact goals, revisions, error messages, and measured size changes |
| `google-deepmind/alphageometry` | HEAD `6777cb586cbb46beed28db12dc72c69770b68337`; Apache-2.0 code, CC-BY-4.0 other materials | Source-level numerical predicates and constructions distinguish reusable incidence, distance, line, circle, and angle operations from the DD+AR solver workflow |

No dataset row was copied into the repository. Dataset answers are public and
contaminated for performance evaluation; they may be used only for open
reproduction and regression.

## Move ledger

| Evidence | State before move | Atomic move | Inspectable output | Consequential use | Failure boundary |
| --- | --- | --- | --- | --- | --- |
| Erdős 205 and 370 | Candidate integer or construction | Factor integer; count prime multiplicities; select largest prime factor | Complete prime-power map and divisors | Accept or reject smoothness and factor-bound arguments | Zero has no finite factorization; failure is not a number-theoretic conclusion |
| Erdős 401 | Factorial divisibility claim | Compute factorial and prime valuations | Exact decimal integer or valuation | Check divisibility inequalities and choose parameters | Valuation requires a nonzero integer and a prime base |
| Erdős 124 | Candidate base representation | Expand one integer into positional digits | Separate sign, base, and ordered digit artifact | Test distinct-power representation constraints | Only a single bounded representation is computed; no eventual-coverage claim |
| Erdős 707 and issue 1137 | Finite Sidon witness and modulus | Intersect, compare, count, and test finite sets; compute modular residues | Sorted finite-set or modular artifact | Detect witness containment and domain-edge errors such as modulus zero | No claim that a finite witness extends to a perfect difference set |
| Formal Conjectures graph threads | Explicit invariant values | Exact gcd, products, sums, means, ceilings, and sequence transforms | Canonical integer/rational values and sequences | Check a final numerical contradiction or inspect degree-sequence evolution | These primitives do not certify graph semantics that produced the numbers |
| BrokenMath adversarial rows | Original problem plus altered predicate | Decide the exact small predicate independently of the supplied prose solution | Boolean result bound to exact input | Reject a solution whose arithmetic no longer establishes the changed claim | A Boolean primitive decides only its advertised bounded predicate |

## Candidate gate

| Gate | Evidence and decision |
| --- | --- |
| Recurrence | Integer factor/divisor, exact counting, finite-set, rational, modular, and sequence moves recur across independent Erdős, Formal Conjectures, proof-trace, and adversarial datasets. Fine-grained IDs use the fundamental-primitive exception where one result has broad reuse and a maintained backend. |
| Leverage | Each output can change a later divisibility, enumeration, bound, witness, or representation decision without forcing a workflow strategy. |
| Atomicity | Every invocation computes or decides one named domain outcome. Inputs and results remain separately inspectable artifacts. |
| Portfolio fit | Existing determinant, rank, polynomial factor, graph property, case partition, SAT/SMT, and Lean outcomes were not duplicated. |
| Backend readiness | SymPy is already locked and its version is bound into the source-owned `jacobian.primitive-math` provider identity. Python and SymPy exact arithmetic remain distinguishable from an independent checker. |
| Contract honesty | Pydantic validates the complete request before artifact writes. Inputs are bounded. Results use a closed exact-value union. Scope, completeness, provider version, and computed assurance are explicit. |
| Trust boundary | No independent checker exists in this batch, so no result or relationship is `VERIFIED`. |
| Reproduction | Every ID has a completing exact micro-case; invalid modular inverse provides an adversarial fail-closed case. Domain-specific public reproductions are listed above. |
| Evaluation hypothesis | Compare the full primitive portfolio with an ablation excluding these IDs on held-out factor/divisibility, finite-set, congruence, and exact-counting tasks. Measure correctness, false certification, discovery errors, calls, tokens, and time. |

## Deferred and rejected candidates

The source bundle also suggests graph spectral invariants, graph products,
distance matrices, proof-tree materialization, proof-edit checking, premise
dependency retrieval, Euclidean constructions, Gröbner bases, lattice
reduction, group computations, and validated numerical bounds. They are not
part of this batch because nearby catalog overlap, a missing typed contract, a
missing independent checker, or a heavier backend requires separate work.

Rejected shapes include:

- one capability per dataset column or backend function;
- opaque conjecture solvers and proof generators;
- generic `sympy.eval`, arbitrary Python, or command execution;
- self-verifying search results;
- unbounded enumeration disguised as complete; and
- claims that a failed factorization, search, or predicate establishes a
  theorem.

The `sabakublashvili/idef-geobench` card is also deferred as row-level
evidence. Its card describes a 40-problem strict DSL benchmark but explicitly
contains placeholder instructions to edit field names, while the Dataset
Viewer exposes a single `text` column whose first row is only an excerpt
notice. AlphaGeometry source independently supports the underlying geometry
predicate candidates; GeoBench does not yet supply a pinned, inspectable
40-row reproduction corpus for them.

## Exact rational geometry batch

AlphaGeometry's pinned source independently exposes point, line, circle,
incidence, angle, ratio, and construction primitives beneath its DD+AR solver.
The solver workflow, learned search, and floating tolerance checks were
rejected. Thirteen fundamental coordinate outcomes use the single-source
fundamental-primitive exception with Jacobian's already pinned SymPy backend:

- squared distance and midpoint;
- exact collinearity and concyclicity;
- line parallelism, perpendicularity, and intersection classification;
- orthogonal point projection;
- triangle orientation, centroid, and circumcircle;
- polygon signed area; and
- finite planar convex hull.

Every capability accepts only canonical rational coordinates, validates line
degeneracy before computation, returns a result-specific schema, preserves
input and result artifacts, and reports `COMPUTED` assurance. Collinear
circumcircle input and a line with repeated defining points fail without
writing operation artifacts. These operations do not prove a synthetic
geometry theorem and do not expose AlphaGeometry's multi-stage solver.

Some closely related elementary IDs may prove too fine-grained in autonomous
use. Keep them experimental until a held-out ablation determines whether
descriptor search is usable or whether selected operations should consolidate
into batched domain capabilities without hiding intermediate values.

## Graph counterexample-invariant expansion

Exact Formal Conjectures threads repeatedly expose graph invariants as
independent move episodes: P5 uses eccentricity and domination witnesses;
WOWII 59 uses Havel--Hakimi residue, induced-subgraph orders, and a final exact
ceiling; WOWII 103 uses triangle frequency and average eccentricity; WOWII 109
uses residue and independence; TxGraffiti 4 uses harmonic index and saturation
number.

The existing batched `graph.compute.properties` capability was therefore
expanded instead of adding overlapping IDs. It now computes requested
properties lazily and adds girth, diameter, radius, vertex eccentricities,
average eccentricity, triangle frequencies, exact harmonic index,
Havel--Hakimi trace, and residue. A P5 reproduction checks all nine results.
Distance properties on a disconnected graph return an execution error and no
mathematical conclusion. Saturation number, total domination, and largest
induced forest/tree/bipartite orders remain deferred: their exponential search
needs explicit graph-order budgets and result-specific witnesses before the
contract can honestly claim an optimum.

## Public reproduction and evaluation handoff

The integration suite invokes all 108 IDs with valid bounded inputs, checks
catalog uniqueness and installation, checks representative exact outputs and
artifact relationships, and checks that an inapplicable modular inverse returns
an execution error with heuristic assurance and no operation artifacts. The
geometry suite invokes all 13 coordinate capabilities and exercises degenerate
lines and collinear circumcircles. The graph suite reproduces all nine added
P5 invariants and rejects disconnected distance properties.

A comparative evaluation should freeze:

1. factor-multiplicity and factorial-divisibility cases derived from new,
   uncontaminated integer templates;
2. finite-set and modular cases with zero-modulus, non-coprime, duplicate, and
   boundary traps;
3. exact rational inequalities used downstream in a graph or combinatorics
   claim;
4. a control catalog excluding all 108 IDs; and
5. an independent oracle that recomputes results without importing this
   adapter.

Public source cases must not serve as hidden oracles.

## Opportunity termination audit

The resulting catalog contains 157 distinct capability IDs: 121 were added by
this research pass (108 primitive and 13 geometry), while nine graph outcomes
were added to the existing property batch. A final domain pass compared the
remaining spreadsheet clusters with the complete catalog.

- Algebra and matrix sources repeatedly motivate polynomial factorization,
  Jacobian computation, exact map evaluation, identity and solution replay,
  determinant, rank, rational linear solution, and Hermite normal form. Those
  outcomes already exist. Polynomial GCD, resultant, discriminant, Gröbner
  basis, RREF, nullspace, characteristic polynomial, Smith normal form, and
  lattice reduction remain plausible, but the inspected rows did not isolate
  a recurring agent decision beyond exposing backend functions. They need
  move-level cases and, for normal forms or bases, canonicalization and
  certificate contracts.
- Formal proof, premise-retrieval, proof-tree, and proof-compression sources
  motivate better theorem-state artifacts and evaluation corpora. They do not
  justify pretending retrieval, tactic search, or proof generation is one
  mathematical outcome. Existing Lean checking and artifact capabilities are
  the appropriate boundary until a typed intermediate is specified.
- Optimization, probability, analysis, and numerical sources suggest validated
  bounds, moment calculations, and rational certificates. No maintained
  backend plus result-specific checker was established for a sufficiently
  recurring atomic outcome in this pass.
- Graph saturation, domination variants, and maximum induced substructures
  have concrete recurrence, but require explicit order budgets and witnesses
  before an optimum can honestly be reported. Graph spectral and product
  operations need a sharper consequential-use case than raw invariant
  enumeration.
- Dataset columns, benchmark metadata, arbitrary symbolic evaluation, generic
  code execution, opaque solvers, and one-ID-per-library-function shapes fail
  atomicity, portfolio-fit, or trust-boundary gates.

Thus the pass stops at the last evidence-backed, contract-ready opportunity,
not at an arbitrary numeric quota. Deferred items are a queue for new evidence
or held-out evaluation, not implied negative results.
