# Resource-derived task selection

Review date: 2026-07-30. Source inventory: the `Resources` tab of spreadsheet
`1_p_kvBZBwG5f9M48rkPv9_Mfc0K00NQXR6akGkYqNzI`.

## Accepted

| Task | Difficulty | Category | Frozen source | Why it remains useful |
| --- | --- | --- | --- | --- |
| `autoformalization-semantic-audit` | Hard | Autoformalization / semantic alignment | ProofNetVerif valid row 2 (`Rudin\|exercise_1_18a`), revision `91183e5…` | Adds exact semantic auditing of a proposed formal statement: expose both a dropped premise and an operator substitution using independently checked finite-dimensional witnesses, without treating type checking as semantic equivalence. |
| `matrix-square-zero-counterexample` | Easy | Linear algebra / counterexample | COUNTERMATH, test row 2, revision `d4e9f8c…` | Minimal exact witness; tests hypothesis discipline without duplicating an existing task. |
| `polynomial-tail-counterexample` | Medium | Polynomial reasoning / counterexample | DeepTheorem, train row 8 (source id 3172), revision `f593572…` | Requires roots, tail scope, and an exact order witness; verifier accepts any valid witness. |
| `subspace-direct-sum-counterexample` | Hard | Linear algebra / quantifiers | COUNTERMATH, test row 8, revision `d4e9f8c…` | Tests careful interpretation of distinct indices and exact reconstruction of all local conditions. |
| `log-exponent-recovery` | Hard | Algebra / logarithms | Discover-and-Prove `minif2f_hard`, train row 1, revision `ac10444…` | Compact exact derivation with a stable arithmetic oracle and a different reasoning pattern. |
| `calendar-good-days-audit` | Medium | Proof audit / bounded verification | BrokenMath, benchmark row 84, revision `5eda8c5…` | Requires a complete finite audit rather than trusting a false target; the verifier reconstructs all qualifying dates. |
| `random-function-expectation-audit` | Hard | Proof audit / probability | BrokenMath, benchmark row 88, revision `5eda8c5…` | Tests dependence-aware expectation reasoning and exact probability bookkeeping, a pattern absent from the pending suite. |
| `euler-line-symbolic-certificate` | Hard | Euclidean geometry / symbolic theorem verification | IDEF-GeoBench, curated problem 1 (hosted rows 2-17), revision `ce1decbe…` | Adds a new geometry workflow: derive generic rational coordinates, satisfy the point-defining identities, and certify a universal incidence relation exactly. |
| `grounded-premise-proof` | Medium | Theorem retrieval / proof reconstruction | NaturalProofs-Gen train row 524 (source id `[508,0]`), revision `bdf4123…` | Adds premise selection with true distractors and a replayable proof DAG: the verifier checks normality, quotient formation, representative commutation, and equality chaining without trusting the source proof text. |
| `metric-tsp-proof-repair` | Hard | Proof repair / graph optimization | forge-reason-v1, validation row 11 (`forge-reason-00218`), revision `e582eb0…` | Adds proof repair rather than another verdict-only audit: identify an unjustified equality, weaken the theorem to its valid approximation guarantee, and bind the repair to an exact independently optimized trace. |
| `modular-cubic-obstruction` | Medium | Number theory / impossibility certificate | Discover-and-Prove `minif2f_hard`, train row 195 (`numbertheory_4x3m7y3neq2003`), revision `ac10444…` | Adds a universal Diophantine nonexistence workflow: discover a modulus, enumerate a complete residue certificate, and have an independent checker test every residue pair. |
| `divisibility-construction-witness` | Medium | Number theory / construction search | MathOlympiadBench row 57 (`Imo1984P2`), revision `1397f5e…` | Adds existential construction rather than proof of a fixed answer: any bounded pair satisfying both divisibility constraints is accepted after exact independent recomputation. |
| `log-inequality-meta-audit` | Hard | Conversation proof audit / meta-verification | Nemotron-Math-Proofs-v2 rows 54-55, revision `7665d7f…` | Adds a four-layer audit: distinguish a false universal claim, a mathematically valid disproof, noncompliance with the original “prove” instruction, and whether the evaluator and meta-evaluator scores follow their stated rubrics. |

Difficulty is based on the complete task contract, not only the length of the
answer. The suite deliberately contains no Extreme/Open task: the reviewed
open-problem resources did not provide a stable, independently executable
rubric compatible with this scored dataset.

## Discarded

The remaining inventory was not converted wholesale. Major rejection classes:

- Dataset indexes, leaderboards, tool pages, model cards, tutorials, and
  duplicated mirrors are resources rather than benchmark problems.
- Repeated arithmetic and theorem-corpus items would add volume without a new
  reasoning or verification pattern.
- Informal conversations and many conjecture lists lack a frozen objective,
  complete assumptions, or a reproducible evaluator.
- Open conjectures and research challenges were not assigned fabricated answer
  keys. They remain candidates for the separate research-challenge workflow
  once a durable partial-progress rubric and postmortem contract exist.
- Problems overlapping the eight pre-existing `regression-v1` workflows
  (SAT witnesses, graph counterexamples, finite partitioning, polynomial
  normalization, polynomial-map collisions, and rational linear solving) were
  skipped.
- Source rows whose correctness or intended quantifier scope could not be
  independently established were discarded rather than repaired silently.
- BrokenMath rows with unbounded complements, ambiguous altered quantifiers,
  or a source derivation that could not be independently reconstructed were
  rejected. Rows 84 and 88 were retained because their complete finite
  evaluators are small, exact, and independent of the published solution.
- Most later Resources rows are formal-prover corpora that require pinned Lean,
  Coq, HOL, or Isabelle runtimes unavailable to this offline suite. They were
  not converted into weak string-matching tasks. Adjacent IDEF-GeoBench rows
  were also skipped: several rely on implicit nondegeneracy, are substantially
  simpler length/incidence consequences, or would repeat the same coordinate
  identity workflow without increasing coverage.
- Nearby forge-reason-v1 rows were rejected when the repair was only a missing
  base case, merely relabeled an open problem, or depended on cryptographic or
  analytic assumptions that the offline verifier could not independently
  adjudicate. The Metric TSP row was retained because every repaired proof
  obligation admits a complete finite checker on a frozen metric instance.
- Discover-and-Prove rows 100–199 were screened beyond the previously used
  logarithm example. Routine evaluations, answer-only algebra, and tasks
  overlapping exact arithmetic were rejected. Row 195 was retained because
  its source answer is absent, its universal integer scope is unambiguous, and
  a complete modular obstruction is independently reproducible offline.
- MathOlympiadBench rows 0–99 were screened for a different source and workflow.
  Broad existence theorems, analysis inequalities, geometry formalizations,
  and classification problems were rejected because a small offline verifier
  could not establish their full claims. Row 57 was retained because it asks
  for an explicit construction and every submitted witness can be checked
  exactly without a Lean runtime or reliance on the published witness.
- Nemotron-Math-Proofs-v2 proof, verification, and meta-verification traces
  were screened as conversation-derived candidates. Already-correct proofs
  with unanimously positive evaluations were rejected because they add little
  diagnostic value, while traces whose correctness depended on uncheckable
  prose were rejected. Rows 54-55 were retained because the mathematical
  counterexample has a compact exact certificate and the disagreement between
  truth, requested direction, evaluator score, and meta-score is explicit.
- ProofNetVerif valid rows 0–99 were screened for semantic mismatches that
  remain independently checkable without a pinned Lean runtime. Rows needing
  topology, extension theorems, or library-specific elaboration were rejected;
  row 2 was retained because both the omitted dimension premise and the
  coordinatewise-for-inner-product substitution admit exact integer-vector
  counterexamples. The dataset's `correct=false` label is provenance only, not
  verifier evidence.
- NaturalProofs-Gen rows 500–599 were screened for grounded theorem retrieval.
  Proofs requiring a large unstated library or prose-only definitions were
  rejected. Row 524 was retained because its quotient-group argument has a
  compact dependency graph, the cited normality and coset-product premises can
  be separated from true distractors, and every inference can be replayed in a
  frozen abstract rule system.

This is a curation record, not a claim that rejected datasets are intrinsically
low quality; they were unsuitable for this specific long-lived Harbor suite.
