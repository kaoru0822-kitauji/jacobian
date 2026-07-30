---
name: develop-math-capabilities
description: Orchestrate Jacobian capability development from research-level challenge mining and agent-trace diagnosis through evidence-gated producer/checker implementation and post-change model-in-the-loop evaluation. Use when asked to find mathematical challenges, run Frontier or postdoc evaluations, turn repeated failures into capability proposals, add the justified tools and independent checkers, compare baseline and treatment behavior, or execute several of those stages as one auditable improvement loop. Route detailed work to discover-math-capabilities, implement-math-capability, implement-math-capability-checker, and evaluate-math-capabilities rather than replacing them.
---

# Develop Math Capabilities

Run one evidence-preserving product-development loop. Keep mathematical
strategy with the evaluated agent and keep each Jacobian capability atomic.

Use the shared handoff in
[`capability-development-handoffs.md`](../../../docs/reference/capability-development-handoffs.md)
between every stage. Do not silently repair a deficient earlier-stage record
inside a later stage.

## Choose the scope

Classify the request before changing code:

| Requested outcome | Start with | Stop or continue |
| --- | --- | --- |
| Find hard cases or decide what is missing | `discover-math-capabilities` | Stop with accepted, rejected, or deferred candidates unless implementation was requested |
| Reproduce current behavior on public challenges | `evaluate-math-capabilities` | Report a public regression or harness validation, not a causal score |
| Judge one concrete portfolio delta | `evaluate-math-capabilities` | Require a frozen control, treatment, oracle, and repeated runs for comparative claims |
| Add an accepted mathematical outcome | `implement-math-capability` | Return to discovery if the candidate or contract is not ready |
| Add stronger assurance | `implement-math-capability-checker` | Require a stable producer and an independently checkable exact claim |
| Run the complete improvement loop | Follow all applicable stages below | End with a portfolio decision and remaining obligations |

Read the selected phase skill completely before performing that phase. Use
this skill only for routing, evidence continuity, stage gates, and iteration;
the phase skills own their detailed standards.

## 1. Freeze the evidence bundle

Read `AGENTS.md` and `CONTRIBUTING.md`. Record:

- source rows, papers, formal artifacts, known solutions, and licenses;
- current Jacobian catalog, provider availability, bounds, and git tree;
- raw agent transcripts, prompts, model settings, failures, and corrections;
- which answers are visible and which oracle material is withheld; and
- the exact question the investigation should distinguish.

Keep downloaded datasets, raw traces, and exploratory ledgers in ignored
storage. Commit versioned challenge cases, generalized process evidence,
contracts, tests, and stable evaluation fixtures.

## 2. Mine and classify challenges

Use `discover-math-capabilities` to reconstruct consequential mathematical
moves from several cases. Include cases that should close with the current
portfolio, cases requiring composition, and deliberate gap probes.

Before proposing a new operation, classify every observed failure:

- an existing capability worked;
- discovery or descriptor quality hid an existing capability;
- the agent selected or parameterized it poorly;
- a contract field, scale bound, artifact, or checker was missing;
- a provider, budget, environment, or authorization blocked execution; or
- mathematical reasoning rather than tooling was the bottleneck.

Fix discovery, examples, defaults, errors, or reusable agent guidance when
those are the actual gap. Require recurring move evidence or a justified
fundamental-primitive exception before adding a capability.

Add public diagnostic cases to the versioned corpus under
`benchmarks/research_challenges/`. Preserve immutable input suites and create a
new status overlay when live portfolio coverage changes. Keep `scored=false`
when the answer is public.

Plan a no-retrieval public run before spending model budget:

```console
uv run python benchmarks/research_challenge.py \
  --challenge CHALLENGE_ID
```

Execute only with explicit model-work authorization and a hard process budget:

```console
uv run python benchmarks/research_challenge.py \
  --challenge CHALLENGE_ID \
  --model MODEL \
  --reasoning-effort xhigh \
  --timeout-seconds 900 \
  --execute \
  --max-model-runs 1
```

Treat the resulting trace as workflow evidence, not proof that Jacobian caused
a correct answer.

## 3. Gate the capability candidate

Produce a `stage=discovery,status=accepted` handoff only when the candidate has:

- one coherent agent-visible mathematical outcome;
- source-backed recurrence and downstream leverage;
- a non-duplicative catalog delta;
- bounded typed inputs and inspectable outputs/artifacts;
- honest exactness, scope, completeness, and failure semantics;
- a maintained backend and understood deployment/license constraints;
- an independent replay path or an explicit open assurance obligation;
- a public reproduction; and
- a falsifiable evaluation hypothesis.

Use `needs_revision`, `rejected`, or `blocked` with exact evidence and a next
action when a gate fails. “No justified new capability” is a valid result.

## 4. Implement the producer

Use `implement-math-capability` from the accepted handoff. Keep the change in
the existing domain bundle and expose one outcome, not an opaque
`solve`/`research` workflow or mechanical backend wrapper.

Add a thin vertical slice:

1. Freeze the Pydantic request and result contracts.
2. Add one failing public behavior or boundary test.
3. Implement full validation before computation or artifact writes.
4. Preserve useful intermediate artifacts, relationships, and obligations.
5. Keep timeout, cancellation, error, incomplete search, and absent witnesses
   as non-conclusions.
6. Cap the producer at `COMPUTED`.
7. Run focused tests, then the repository-prescribed `make check`.

Return `stage=implementation,status=complete` with the exact catalog delta,
validation actually run, runtime/compatibility state, and checker obligations.

## 5. Add independent verification when justified

Use `implement-math-capability-checker` only when stronger assurance changes a
downstream decision and every claimed obligation can be independently replayed.

Freeze an obligation ledger, bind the exact claim/semantics/candidate/scope and
checker identity, establish producer-checker independence, and attack
substitution, mismatch, partiality, timeout, and authorization boundaries.
Only the operator-authorized verified path may emit `VERIFIED`.

Return `stage=checker,status=complete`. Keep unsupported obligations open
instead of weakening the claim.

## 6. Evaluate the portfolio delta

Use `evaluate-math-capabilities` after implementation, or earlier when a
concrete pre-implementation intervention is already runnable.

Separate two evaluation classes:

- **Public reproduction:** validate contracts, discovery, composition,
  fail-closed behavior, and regression coverage. Never report it as held-out
  model performance.
- **Comparative evaluation:** keep the oracle inaccessible, freeze one
  intervention dimension, use the same visible task/model/budget/environment,
  randomize condition order, and run enough repetitions for the stated claim.

Use the repository-local `harbor-benchmarks` skill for the committed Harbor
task bundles, Oracle validation, and Jacobian observation job. Run the guarded
`make agent-eval EVAL_EXECUTE=1` entry point rather than creating a custom task
runner. Inspect
Harbor ATIF together with Jacobian telemetry and record the git tree, task
digests, provider/runtime, model/settings, prompt, oracle/verifier identities,
seeds, raw traces, and structured reports.

Compare the observed git, catalog, policy-profile, provider, prompt, and model
fingerprints with the declared evaluation manifest before combining results.
Return `stage=evaluation,status=needs_revision` when they differ; do not relabel
an ad hoc hosted run as evidence from a frozen no-retrieval treatment.

Score correctness, false certification, scope, completeness, and evidence
bindings before tokens, calls, bytes, latency, or tool-selection efficiency.
Distinguish backend defects from descriptor, contract, strategy, and model
sampling variance.

Return `stage=evaluation,status=complete` with a justified keep, expand,
improve, split, consolidate, stabilize, defer, retire, or repeat decision.

## 7. Iterate without laundering evidence

Route each finding to the earliest deficient stage:

- weak recurrence or leverage → discovery;
- unusable or dishonest contract → producer implementation;
- incomplete or non-independent replay → checker implementation;
- leakage, weak oracle, or insufficient repetitions → evaluation;
- agent strategy issue with adequate atomic outcomes → descriptor/example or
  agent-skill improvement.

Create a new versioned challenge/status artifact when facts change. Do not
rewrite historical snapshots, use a public answer as hidden evidence, infer an
all-parameter theorem from more bounded runs, or add a capability merely
because one model failed.

Finish when the requested stage is complete and every remaining issue has an
owner, evidence, and next action. Report the stage transitions, accepted and
rejected decisions, committed artifacts, validations actually run, evaluation
class, and unresolved mathematical or assurance obligations.
