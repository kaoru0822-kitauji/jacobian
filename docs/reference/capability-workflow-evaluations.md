# Capability workflow evaluation plan

[Documentation home](../index.md)

- Status: Active product evaluation plan; capability IDs remain provisional
- Scope: Shaping a broad portfolio of composable mathematical capabilities
  through ablation evidence and portfolio guidance

## Decision

Build a broad portfolio of composable mathematical capabilities, each with one
clear agent-visible outcome, and use held-out evaluations and real transcripts
to improve discovery, examples, ranking, defaults, consolidation, and
retirement. Experimental capabilities may be exposed and invoked before they
are evaluated; evaluation results are evidence-based routing hints and
portfolio guidance, not access restrictions or a prerequisite for availability.

Use the shared `CapabilityResult` contract, freeze realistic workflow tasks and
independent oracles, and record baselines so every slice can be compared against
a no-new-capability condition and against the rest of the portfolio. Agent
transcripts show whether capability discovery, contracts, examples, or
boundaries should change. Absence of evaluation does not block experimental
availability.

Prescribed-tool cases test contract usability and conformance, not portfolio
value. Autonomous portfolio evaluations let agents choose tools and measure how
well the portfolio supports composition. Evaluate complete portfolios and
ablations as well as individual capabilities.

Before stabilizing or recommending a capability, search the installed catalog
by domain, artifact type, and mathematical outcome, then inspect the closest
matches. If an existing capability already exposes the outcome, first test
whether the real need is better discovery, a clearer contract, artifact
handoff, batching, consolidation, or retirement. Run a matched
current-versus-candidate ablation when overlap remains ambiguous or the
decision is consequential. Routine additions do not require exhaustive
pairwise or leave-one-out evaluation.

The current `CapabilityResult` contract makes four composition concerns
first-class:

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

This workflow tests whether first-class scope and completeness let agents use
`case.partition.finite` correctly and whether its contract, examples, or
discovery metadata need adjustment.

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
`property.compute` names are design hypotheses, not a required API. Prefer
specific domain-owned capability IDs over generic verb wrappers; use the
existing transformation and verification machinery for claim edits unless a
held-out workflow shows that a smaller domain-specific capability expresses the
task better. Evaluation informs whether to add, split, or consolidate such
capabilities.

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
Freeze the tree and oracle before the comparison. This ablation measures a
capability's marginal contribution to the portfolio and informs retention,
consolidation, and ranking.

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
and local-premise application closed its goal. The production adapters now use
that maintained JSON protocol rather than parsing Lean's pretty-printed goals.
`lean.proof_state.apply_tactic` materializes one transition, child goals, and
replay source. `lean.retrieve.premises` exposes bounded Mathlib `exact?`
suggestions and declaration references. Neither adapter certifies a theorem;
completed source must still go through `lean.check`.

### Lean declaration-discovery pilot

The 2026-07-26 pilot compared the same Jacobian portfolio under both
conditions. The control server omitted only `lean.declaration.search` and
`lean.declaration.inspect`; both conditions retained `lean.check`. Prompts,
`gpt-5.6-sol`, high reasoning effort, per-condition timeout, output schema, and
hidden checker oracle were matched. The two held-out statements used
`List.revzip` and `Set.image`/`Set.preimage`, not the public square-root
tutorial. The scorer required the report, successful invocation trace,
candidate, claim, certificate, and authorized verification record to bind the
exact statement and proof.

Three valid pairs and one operationally invalid pair were inspected. This is a
small development pilot, not a powered performance comparison:

| Case/run | Condition | Correct | Discovery used | Seconds | Input tokens | Calls | Tool errors | Rejected proofs |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `List.revzip` A | control | yes | no | 88.292 | 278,161 | 7 | 1 | 1 |
| `List.revzip` A | treatment | yes | yes | 376.399 | 486,143 | 12 | 4 | 1 |
| `List.revzip` B | control | yes | no | 214.873 | 250,982 | 6 | 0 | 3 |
| `List.revzip` B | treatment | yes | yes | 440.582 | 615,722 | 15 | 6 | 1 |
| set image/preimage | control | yes | no | 88.583 | 140,217 | 3 | 0 | 0 |
| set image/preimage | treatment | yes | no | 59.424 | 139,035 | 3 | 0 | 0 |

No valid run falsely certified a result, used the shell, or made a parameter
error. In both `List.revzip` pairs, treatment eventually used successful exact
inspection or search results and produced a checker-accepted proof. It did not
improve completion: control also passed. Treatment added 288.107 and 225.709
seconds, 207,982 and 364,740 input tokens, five and nine MCP calls, and three
and six additional tool execution errors. Most errors were Mathlib searches
exhausting the 75-second subprocess budget. The set case did not exercise
discovery in either treatment run, so its elapsed difference is sampling and
runtime variance, not intervention lift.

One additional set pair is excluded from comparative interpretation. Its first
condition passed; the second condition's `lean.check` reported the pinned
toolchain unavailable after registration and returned `UNKNOWN`. The agent
correctly reported heuristic assurance with no record. This is an operational
runtime flake and neither a mathematical failure nor evidence for treatment.

The decision is **revise**. Keep search and exact inspection available as
separate experimental atomic outcomes, but do not recommend them or expand to
goal stepping and premise application yet. A longer timeout would only hide
the dominant cost. First replace repeated full Mathlib process startup and
scans with a reusable pinned index or persistent query service, keep exact
environment identity, and make catalog discovery compact. Then rerun these
same held-out cases and add cases where direct automation does not already
solve the proposition.

#### Indexed follow-up

The follow-up implementation uses Mathlib's imported module metadata to build
an atomically materialized, environment-bound catalog. Catalog candidates keep
their exact deterministic scan positions; Lean resolves them again and checks
the elaborated type. Exact inspection uses direct environment lookup. The
backend checks the catalog byte digest before and after reuse and rejects
identity changes, partial writes, response-ID mismatches, and tampering.

On the same host, a fresh `List.revzip` search that previously exhausted the
75-second budget completed in 28.886 seconds. Reusing the catalog for the same
three-result query completed in 9.568 seconds, and exact inspection completed
in 9.146 seconds. Fresh and reused searches returned the same three
declarations, `RESULT_LIMIT`, and `scanned_declarations = 145293`. These are
development measurements, not latency guarantees.

One frozen pair per case was then rerun with the same model, effort, oracle,
condition isolation, and 600-second condition budget:

| Case | Condition | Correct | Discovery used | Seconds | Input tokens | Calls | Tool errors | Rejected proofs |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `List.revzip` | control | yes | no | 166.788 | 252,870 | 6 | 0 | 3 |
| `List.revzip` | treatment | yes | no | 170.406 | 299,191 | 6 | 0 | 3 |
| set image/preimage | control | yes | no | 57.268 | 140,354 | 3 | 0 | 0 |
| set image/preimage | treatment | yes | no | 64.866 | 131,915 | 3 | 0 | 0 |

All four runs produced checker-bound exact results with no false
certification, parameter error, tool error, shell use, or operational failure.
The treatment agents did not invoke declaration discovery, so the elapsed and
token deltas are not intervention effects. This rerun shows that merely making
the experimental capabilities available did not add calls or failures; it does
not establish autonomous outcome lift.

The performance revision is accepted at the capability layer. Recommendation
status remains experimental: keep search and inspection separate and evaluate
harder held-out statements where direct automation does not already solve the
proposition before recommending discovery by default. Proof-state exploration
is evaluated separately below.

### Lean portfolio ablation

The Lean evaluation uses four catalogs under the same model, reasoning effort,
prompt, timeout, and output schema:

| Condition | Exploratory Lean capabilities |
| --- | --- |
| baseline | neither capability |
| tactic | `lean.proof_state.apply_tactic` only |
| retrieval | `lean.retrieve.premises` only |
| combined | both capabilities |

All conditions retain `lean.check`. The runner randomizes condition order per
case and repetition and creates isolated workspaces and artifact stores. It
measures exact proof completion, independent replay success, false
certification, parameter and tool errors, model tokens, tool calls, and wall
time. A checker-accepted alternative proof is valid; the scorer does not
require textual equality with the hidden oracle.

The scored tasks are fresh private compositions whose exact theorems are
disjoint from the discovery rows. Their hidden reference proofs remain outside
the agent workspace. Public Hugging Face rows, LeanTree/APRIL examples, blog
posts, Codeforces cases, and repository artifacts are reproduction and
workflow-mining cases only. They never serve as hidden evaluation tasks.

## Source policy

Use the supplied research collection according to evidence strength:

| Source class | Use |
| --- | --- |
| Lean proofs, checker-ready certificates, explicit objects, and pinned code | Workflow mining, independent reproduction, and public regression |
| Maintained proof assistants, CAS/solver libraries, and mathematical databases | Adapter candidates; pin and test their exact versions |
| Curated problem databases and expert forums | Task discovery and premise retrieval; verify status against primary artifacts |
| Public theorem-proving datasets and benchmarks | Baselines, portability checks, and regression after license and statement-alignment review |
| Blogs, news, social threads, and shared chats | Lead generation and workflow clues only |

Machine checking proves the formal statement that was checked. It does not by
itself prove that the formal statement corresponds to the intended informal
conjecture. Statement correspondence remains a separate relationship and
review obligation.

## Rolling evaluation loop

1. Freeze workflow cases, hidden oracle contracts, and baseline metrics.
2. Expose mathematically useful capabilities through
   `capability.describe` and `capability.invoke`, preserving typed artifacts and
   independent verification boundaries.
3. Run autonomous portfolio evaluations and targeted ablations under matched
   model, budget, and sampling conditions.
4. Inspect transcripts for missing operations, discovery failures, redundant
   calls, parameter errors, opaque intermediate state, and false certification.
5. Improve capability contracts, examples, discovery, ranking, or boundaries
   and rerun only the affected evaluations.
6. Add new domains, maintained backends, and historical episodes as their
   inputs and independent oracles become ready.

The loop does not gate capability availability. Experimental capabilities may
be installed before evaluation completes. Evidence guides agent-facing
discovery, recommendations, defaults, consolidation, and retirement while
verification authority remains independent of search, generation, and
evaluation.

[erdos-33]: https://github.com/google-deepmind/formal-conjectures/issues/1347
[erdos-707]: https://github.com/google-deepmind/formal-conjectures/issues/1137
[graph-316]: https://github.com/google-deepmind/formal-conjectures/issues/4133
[leandojo-v2]: https://github.com/lean-dojo/LeanDojo-v2
[lean-repl]: https://github.com/leanprover-community/repl
[pantograph]: https://github.com/leanprover/Pantograph
[wowii-194]: https://github.com/google-deepmind/formal-conjectures/pull/4542
