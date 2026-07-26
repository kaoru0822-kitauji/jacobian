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

### SAT certificate portfolio pilot

The frozen 2026-07-26 SAT pilot compared direct local reasoning with the
four-outcome SAT portfolio under `gpt-5.6-terra`, high reasoning effort, a
600-second per-run limit, and order seed `20260731`. Two private cases created
after the interface freeze were each repeated twice: one satisfiable
14-variable planted formula and one unsatisfiable 12-variable odd-cycle
formula. Their exact clauses remained outside the repository; the recorded
case digests were
`sha256:dca243f518737d9e776bde0c001958dbd98e9fe830e483e47dd5f643671da6ec`
and
`sha256:20dac1be40cf5845b7fdba501933bc8adfcc6487d88205273917a7fda84cf4f1`.

Both conditions received the same pre-materialized canonical CNF URI. Control
had no MCP server and could use local code. Treatment used Jacobian and had to
compose the applicable producer and verifier. This isolates the value of
`sat.model.find`, `sat.model.verify`, `sat.unsat_proof.find`, and
`sat.unsat_proof.verify`; it does not evaluate a CNF-authoring capability.

The hidden scorer brute-forced the exact CNF, limited private cases to at most
20 variables, checked the report against the durable CNF and evidence,
required an ordered producer-to-verifier invocation trace, and reopened a
clean kernel to replay the checker. Public SAT reproductions were explicitly
unscored.

| Condition | Passed | False certifications | Independent replay | Median seconds | Median input tokens | Median calls | Tool errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| control | 4 / 4 | 0 | 0 / 4 | 17.258 | 12,904.0 | 0 | 0 |
| SAT portfolio | 4 / 4 | 0 | 4 / 4 | 39.788 | 184,739.5 | 7 | 0 |

Every treatment composed the appropriate evidence producer and independent
verifier, preserved exact bindings, and replayed successfully. Control also
answered every case correctly, but could only report `SELF_CHECKED` and
`UNVERIFIED`. This small pilot supports retaining all four outcomes for their
durable assurance value. It demonstrates no autonomous completion or
efficiency lift. Treatment was substantially slower and more token-intensive,
largely because catalog discovery returns the full installed portfolio.

Development runs exposed three interface issues before the frozen pilot.
They are excluded from the frozen comparison because their cases informed
contract changes. The report contract did not initially distinguish producer
evidence from the verifier's witness or certificate. The client then guessed
nonexistent generic artifact-read capabilities. Finally, a SAT assignment
artifact exposed canonical variable order and positional values on separate
objects, and agents joined those values against the prompt's original order.
The report schema now identifies `assignment_uri` or `proof_uri` as producer
evidence, and `sat.model.find` returns its constructed assignment as an inline
name-to-Boolean map beside the durable URI. A development rerun of the
previously failing noncanonical-order case then passed with clean replay and no
tool error.

The remaining portfolio work is compact catalog discovery and ranking, not
consolidation of the SAT outcomes. The frozen sample is too small for a powered
comparative claim; add new cases and repetitions without reopening these cases
for tuning.

### SMT Carcara contract pilot

The frozen 2026-07-26 SMT pilot used `gpt-5.6-terra`, high reasoning effort,
a 600-second per-run limit, and one repetition of two private `QF_UF` cases.
One case was a direct Boolean contradiction whose cvc5 1.3.4 Alethe proof was
accepted by the pinned strict Carcara checker. The other used equality
transitivity; cvc5 produced two holes and verification had to reject it. The
case digests were
`sha256:5a064aaabc5e83064dd9c864200826522ab47c5e0d955e0fa3130417f2687f4c`
and
`sha256:b30099a1188a4cc16335e9d0f9300abd4a26f034d3202cb1fc84f644ae872704`.

Control decided each exact query directly and could report only
`SELF_CHECKED/UNVERIFIED`. Treatment was prescribed the two exact capability
IDs, had to compose `smt.unsat_proof.find` with
`smt.unsat_proof.verify`, and had to preserve rejection rather than treating a
solver status, zero lexical holes, or proof artifact as verification. The
hidden scorer checked the durable problem/proof binding, ordered invocation
trace, expected verifier status, and a clean-kernel replay.

| Condition | Passed | False certifications | Clean replay behavior | Median seconds | Median input tokens | Median calls | Tool errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| control | 2 / 2 | 0 | 0 / 2 | 11.805 | 12,572.5 | 0 | 0 |
| SMT producer + verifier | 2 / 2 | 0 | 2 / 2 | 36.213 | 101,213.5 | 4 | 0 |

The accepted case created an independently replayable verification record.
The holey case preserved the exact producer artifacts but reported
`COMPUTED/UNVERIFIED`; the scorer observed one expected capability rejection
and no false certification. This supports retaining the producer/verifier
split and the zero-hole, strict-Carcara gate. It does not establish broad
`QF_UF` rule coverage or justify admitting arithmetic logics.

Two development pairs are excluded. A benchmark routing bug initially
overwrote the SMT condition with an unrelated workflow prompt; the scorer
correctly rejected the resulting cross-claim verification record. A separate
development run requested the full capability catalog and consumed about
682,000 input tokens. After selecting the intended condition and describing
the two exact IDs directly, frozen treatments used four calls and about
101,000 median input tokens. Exact descriptors remain too context-heavy, so
compact schema discovery and ranking remain portfolio-level follow-up work.
Because this was a prescribed-capability pilot, it measures contract use and
assurance discipline rather than autonomous portfolio discovery.

### Python-FLINT rational-solution pilot

The frozen 2026-07-26 Python-FLINT pilot used `gpt-5.6-terra`, high reasoning
effort, a 600-second per-run limit, and one repetition of two private exact
rational systems. One was a square three-variable system and one was an
overdetermined four-equation, three-variable system. Their case digests were
`sha256:5bc8e162c74075f5c8e67cb3708ec4bb98a5488b8cd11b6268eca2311a945172`
and
`sha256:69ef3f37d3b9a372eb7bd31c2fca42ca2e985443bf0230a5d7d882a2d710b571`.

Control solved each system directly and could report only
`SELF_CHECKED/UNVERIFIED`. Treatment was prescribed the exact capability IDs
`linear.rational_solution.find` and
`linear.rational_solution.verify`. It had to preserve declared variable order,
pass the producer's `solution_uri` to the verifier, and report `VERIFIED` only
with the returned verification-record URI. The hidden scorer checked every
equation with an independent exact oracle, durable system and vector bindings,
the ordered invocation trace, and clean-kernel replay.

| Condition | Passed | False certifications | Clean replays | Median seconds | Median input tokens | Median calls | Tool errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| control | 2 / 2 | 0 | 0 / 2 | 19.488 | 12,754 | 0 | 0 |
| Python-FLINT producer + verifier | 2 / 2 | 0 | 2 / 2 | 36.692 | 111,162 | 4 | 0 |

Both treatments composed the intended operations without parameter errors or
capability rejection, and both records replayed independently. Agent feedback
reported no missing mathematical operation. This supports retaining the
atomic producer/verifier split and its ordered-vector contract. It does not
show an accuracy gain over direct work on these small systems; its observed
value is durable exact evidence and an independent promotion boundary.

One earlier development dispatch is excluded: the response schema represented
the solution as an open-keyed object, which the model API rejected before any
tokens or tool calls. The frozen schema uses an ordered array aligned with the
declared variables. Treatment still used about 111,000 median cumulative input
tokens and about 17 seconds more wall time than control, so compact descriptor
discovery and lower-overhead MCP composition remain follow-up work. Because
this was a prescribed-capability pilot, it measures contract use and assurance
discipline rather than autonomous portfolio discovery.

### Python-FLINT Hermite-normal-form pilot

The frozen 2026-07-26 HNF pilot used `gpt-5.6-terra`, high reasoning effort, a
420-second per-run limit, and one repetition of two private exact integer
matrices. One was a three-by-four matrix and one was a singular four-by-three
matrix with a zero row. Their case digests were
`sha256:947a2f92b36cc8003b6d990dc9522f3b6a1cc2819085dded794947699b71320d`
and
`sha256:671188addd5934fb2a6b9d95ced1d0aaad819eaa354c16128e0d0af68ecaab38`.

Control computed `H` and `U` directly and could report only
`SELF_CHECKED/UNVERIFIED`. Treatment was prescribed
`matrix.normal_form.hermite` and
`matrix.normal_form.hermite.verify`. It had to pass the producer's
`normal_form_uri` into the verifier and copy the exact matrices and durable
URIs. The hidden scorer independently checked `H = U A`, `det(U) = ±1`, every
FLINT row-HNF condition, artifact bindings, the ordered invocation trace, and
clean-kernel replay.

| Condition | Passed | False certifications | Clean replays | Median seconds | Median input tokens | Median calls | Tool errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| control | 2 / 2 | 0 | 0 / 2 | 73.804 | 40,787.5 | 1.5 | 0 |
| Python-FLINT producer + verifier | 2 / 2 | 0 | 2 / 2 | 41.524 | 104,488.5 | 4 | 0 |

Both treatments used the intended capabilities without parameter errors,
capability rejection, or operational failure. Both verification records
replayed independently. The treatment was faster on these cases but consumed
more cumulative input tokens, so the small pilot does not establish a general
runtime advantage. It supports retaining the complete `H, U` output, the
producer/verifier split, and direct URI handoff without another contract
revision. As a prescribed-capability pilot, it measures usability and
assurance discipline rather than autonomous portfolio selection.

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
