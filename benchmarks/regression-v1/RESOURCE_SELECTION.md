# Resource-derived task selection

Review date: 2026-07-30. Source inventory: the `Resources` tab of spreadsheet
`1_p_kvBZBwG5f9M48rkPv9_Mfc0K00NQXR6akGkYqNzI`.

## Accepted

| Task | Difficulty | Category | Frozen source | Why it remains useful |
| --- | --- | --- | --- | --- |
| `matrix-square-zero-counterexample` | Easy | Linear algebra / counterexample | COUNTERMATH, test row 2, revision `d4e9f8c…` | Minimal exact witness; tests hypothesis discipline without duplicating an existing task. |
| `polynomial-tail-counterexample` | Medium | Polynomial reasoning / counterexample | DeepTheorem, train row 8 (source id 3172), revision `f593572…` | Requires roots, tail scope, and an exact order witness; verifier accepts any valid witness. |
| `subspace-direct-sum-counterexample` | Hard | Linear algebra / quantifiers | COUNTERMATH, test row 8, revision `d4e9f8c…` | Tests careful interpretation of distinct indices and exact reconstruction of all local conditions. |
| `log-exponent-recovery` | Hard | Algebra / logarithms | Discover-and-Prove `minif2f_hard`, train row 1, revision `ac10444…` | Compact exact derivation with a stable arithmetic oracle and a different reasoning pattern. |
| `calendar-good-days-audit` | Medium | Proof audit / bounded verification | BrokenMath, benchmark row 84, revision `5eda8c5…` | Requires a complete finite audit rather than trusting a false target; the verifier reconstructs all qualifying dates. |
| `random-function-expectation-audit` | Hard | Proof audit / probability | BrokenMath, benchmark row 88, revision `5eda8c5…` | Tests dependence-aware expectation reasoning and exact probability bookkeeping, a pattern absent from the pending suite. |

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

This is a curation record, not a claim that rejected datasets are intrinsically
low quality; they were unsuitable for this specific long-lived Harbor suite.
