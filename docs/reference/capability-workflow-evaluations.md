# Capability workflow evaluation plan

[Documentation home](../index.md)

- Status: Active product evaluation plan; capability IDs remain provisional
- Scope: Selecting the smallest useful mathematical capability set
- Compatibility: The v0.2 verification contract remains normative

## Decision

Do not implement a broad vocabulary of mathematical verbs first. Stabilize the
shared result contract, freeze realistic workflow tasks and independent
oracles, record a no-new-capability baseline, and then add one vertical slice at
a time. A capability ID is retained only when agent transcripts show that it
improves correctness or resource use without increasing false certification.

`CapabilityResult` version 2 therefore makes four composition concerns
first-class before adding domain operations:

- exact scope, with domain-owned parameters or a scope artifact;
- completeness as `NOT_APPLICABLE`, `UNKNOWN`, `PARTIAL`, or `COMPLETE`, with
  a separate assurance level and basis;
- relationships between exact source and target artifacts;
- materialized proof obligations and their open or discharged state.

A failed execution cannot report complete coverage. A verified relationship,
discharged obligation, or verified completeness claim must use the same
operator-authorized verification record as the verified result. Every
first-class artifact reference must also appear in `artifact_uris`. The record
must bind the exact relationship artifacts and relation ID, the exact
obligation artifact, or an explicit scope artifact with compatible checked
coverage; sharing an otherwise valid record URI is not enough.

## Initial workflows

The first evaluation set exercises four workflows. These are agent objectives,
not capability names.

### Challenge a universal finite-graph claim

The agent must formalize the exact claim, construct or retrieve candidate
graphs, compute relevant properties, search or mutate candidates, and replay a
counterexample certificate. The oracle includes an explicit graph and an
independent checker. A tempting failure is to promote a successful solver call
or a bounded search with no witness.

The open [WOWII Conjecture 194 pull request][wowii-194] is useful workflow
evidence: it exposes an 18-vertex graph, a graph6 representation, property
claims, and an immutable Lean proof. It is a public regression source, not a
hidden answer and not evidence that the upstream pull request has been
accepted.

### Construct and compare constrained objects

The agent must find at least one object satisfying several exact constraints,
compare multiple candidates using a mix of exact and approximate properties,
and preserve the evidence type of each property. Alternative valid strategies
include solver-backed construction, bounded enumeration, database retrieval,
and mutation from a seed object.

The initial domain is finite simple graphs because maintained infrastructure is
available: NetworkX for graph operations, Z3 for constraint models, and
specialized graph databases or canonical-labeling systems where their pinned
contracts fit. Jacobian should not reimplement graph traversal, SAT/SMT search,
or graph isomorphism algorithms.

### Partition a finite domain and verify coverage

The agent proposes cases, refines them if necessary, and independently checks
that their union equals the declared finite scope. Disjointness is reported
separately. The negative fixtures include a missing boundary value, overlapping
cases, a timeout after partial enumeration, and a partition whose prose
description differs from its executable scope.

This workflow tests whether first-class scope and completeness are useful
before `case.partition` earns a stable capability contract.

### Decompose a Lean goal and apply retrieved premises

The agent inspects a pinned Lean proof state, proposes alternative
decompositions, retrieves candidate declarations, applies premises, and asks
Lean to replay the completed proof. A decomposition remains an unverified
relationship until the parent-from-children obligation is accepted.

Prefer a thin adapter over a custom Lean protocol. Spike the maintained Lean 4
[REPL][lean-repl] first; compare [Pantograph][pantograph] when its higher-level
goal operations materially improve the held-out runs. Do not start new work on
the deprecated LeanDojo v1 interface; evaluate [LeanDojo v2][leandojo-v2] or a
current premise-search system separately when retrieval becomes the measured
bottleneck.

## Capability hypotheses

The workflows justify the following initial experiments:

- `graph.search.atlas`, now implemented as a bounded, exact-order construction
  slice over NetworkX's maintained Graph Atlas;
- `graph.compute.properties`, now implemented with batched properties and
  per-property exactness and backend labels;
- controlled graph mutation only if construction transcripts need it;
- finite case partitioning with a replayable coverage artifact;
- Lean goal-state interaction and premise retrieval, consolidated or split
  according to tool-call and parameter-error evidence.

Generic `claim.derive`, `goal.decompose`, `premise.apply`, and
`property.compute` names are design hypotheses, not an initial required API.
Use the existing transformation and verification machinery for claim edits
until a held-out workflow demonstrates that a smaller domain-specific
capability cannot express the task.

## Evaluation construction

Public conjecture repositories and datasets inform task shape and provide
regression cases, but answer-rich public items are not held out. Create the
scored cases from private templates or generated variants with:

1. a frozen input bundle visible to the agent;
2. a hidden, versioned oracle unavailable in the agent workspace;
3. an independently implemented checker or proof replay;
4. at least one tempting incomplete, misbound, or semantically mismatched path;
5. multiple accepted strategies when the mathematics permits them;
6. a contamination record containing source lineage and cutoff date.

The Formal Conjectures reports on [Erdős 33][erdos-33] and
[Erdős 707][erdos-707] supply particularly valuable negative patterns. One
reverses an existential upper-bound statement into a universal lower bound;
the other shows how admitting `n = 0` flips a formalized variant's truth value.
The [P5 report for Graph Conjecture 316][graph-316] supplies a small explicit
counterexample and a warning that “no counterexample through size 8” is only a
bounded observation.

Measure for each condition and case:

- oracle correctness and false certification;
- wall time and model token use;
- tool-call count, tool execution errors, and parameter errors;
- completion status and completeness label;
- evidence and verification-record bindings;
- whether an accepted alternative strategy was rejected by the scorer.

Run a paired control without the new capability and a treatment with it under
the same model and reasoning budget. Repeat enough times to expose variance.
Freeze the tree and oracle before the comparison.

## Development pilot evidence

The 2026-07-25 development pilot used the same configured model, medium
reasoning effort, prompt, and output contract within each pair. The runner
randomized condition order and recorded the fixture/order seed. The Codex
provider does not expose a generation seed, so provider sampling was not
deterministic. These single-pair results validate the harness and expose tool
friction; they are not a statistically powered performance claim.

| Case | Condition | Correct | False certification | Seconds | Input tokens | Output tokens | Tool calls | Tool/parameter errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| six-vertex path | control | yes | 0 | 15.117 | 20,294 | 300 | 0 | 0 / 0 |
| six-vertex path | graph capabilities | yes | 0 | 67.443 | 195,524 | 901 | 5 | 0 / 0 |
| triangle-free counterexample | control | yes | 0 | 11.567 | 20,299 | 450 | 0 | 0 / 0 |
| triangle-free counterexample | graph capabilities | yes | 0 | 82.879 | 141,165 | 750 | 4 | 0 / 0 |
| finite residue partition | control | yes | 0 | 8.070 | 20,176 | 221 | 0 | 0 / 0 |
| finite residue partition | verified capability | yes | 0 | 48.071 | 90,425 | 744 | 2 | 0 / 0 |

The initial counterexample treatment found the right artifact and exact
properties but failed provenance scoring: `graph.search.atlas` returned an
artifact URI and properties without the graph payload, so the agent supplied a
valid isomorphic relabeling it could not bind to that URI. Returning the small
typed graph payload inline removed the ambiguity, and the repeated treatment
passed without parameter errors or false certification.

This transcript evidence supports keeping `graph.search.atlas` and
`graph.compute.properties` separate: the second call consumed the first call's
exact graph artifact, and the scorer observed the ordered dataflow. It also
supports making returned artifacts inspectable without another generic storage
tool. It does **not** justify graph mutation or Z3 construction: both held-out
tasks were solved within Graph Atlas with zero parameter errors. Treatment was
substantially slower and more token-intensive in this pilot, so the current
slice has correctness/provenance value but no demonstrated efficiency benefit.
Run more repetitions before making a comparative performance claim.

The finite-partition slice is exposed as `case.partition.finite`. Explore mode
materializes the scope, proposed partition relationship, and open coverage
obligation. Verify mode creates a certificate bound to the exact scope, claim,
and partition; an operator-authorized checker in `jacobian_checkers` recomputes
membership, coverage, and optional disjointness without importing the
generator. Missing, outside, and overlapping elements remain unverified and
cannot discharge the obligation. Its single paired pilot passed both
conditions; only the treatment produced an exhaustive checker-bound record.
As with the graph pilot, this establishes correctness and assurance behavior,
not an efficiency improvement.

The pinned Lean REPL spike used upstream tag `v4.31.0`, commit
`0cc60263319308000bbaa5354427f775fe3dc7d0`, against Lean 4.31.0 commit
`68218e876d2a38b1985b8590fff244a83c321783`. Two protocol tasks completed in
2.196 seconds with no parameter errors: `constructor` exposed two child goals
and local-premise application closed its goal. The REPL currently cannot turn a
completed tactic state back into the originating command or a replayable proof
artifact. This is enough to retain the pinned spike, but not enough to add
`goal.decompose` or premise-retrieval capabilities. A later paired agent
evaluation must show outcome value; completed source must still go through
`lean.check`.

## Source policy

Use the supplied research collection according to evidence strength:

| Source class | Use |
| --- | --- |
| Lean proofs, checker-ready certificates, explicit objects, and pinned code | Workflow mining, independent reproduction, and public regression |
| Maintained proof assistants, CAS/solver libraries, and mathematical databases | Adapter candidates; pin and test their exact versions |
| Curated problem databases and expert forums | Task discovery and premise retrieval; verify status against primary artifacts |
| Public theorem-proving datasets and benchmarks | Baselines, compatibility, and regression after license and statement-alignment review |
| Blogs, news, social threads, and shared chats | Lead generation and workflow clues only |

Machine checking proves the formal statement that was checked. It does not by
itself prove that the formal statement corresponds to the intended informal
conjecture. Statement correspondence remains a separate relationship and
review obligation.

## Revised implementation order

1. Freeze these workflow cases, hidden oracle contracts, and baseline metrics.
2. Stabilize first-class scope, completeness, relationships, and obligations.
3. Implement the graph construction/property slice using maintained libraries.
   The first slice uses NetworkX's Graph Atlas and exact graph algorithms;
   solver-backed construction remains a later comparison for orders outside
   the atlas.
4. Run the paired evaluation and keep, split, or consolidate the graph
   capabilities from transcripts.
5. Implement finite partition coverage and rerun the evaluation.
6. Spike the pinned Lean REPL integration, then add decomposition or retrieval
   only where the measured workflow needs it.
7. Decompose compatibility workflows only after the new slices preserve their
   artifacts and assurance boundaries.

This reorders the earlier proposal in one important way: evaluation design and
baseline collection precede capability implementation, and evaluation runs
after every vertical slice rather than at the end.

[erdos-33]: https://github.com/google-deepmind/formal-conjectures/issues/1347
[erdos-707]: https://github.com/google-deepmind/formal-conjectures/issues/1137
[graph-316]: https://github.com/google-deepmind/formal-conjectures/issues/4133
[leandojo-v2]: https://github.com/lean-dojo/LeanDojo-v2
[lean-repl]: https://github.com/leanprover-community/repl
[pantograph]: https://github.com/leanprover/Pantograph
[wowii-194]: https://github.com/google-deepmind/formal-conjectures/pull/4542
