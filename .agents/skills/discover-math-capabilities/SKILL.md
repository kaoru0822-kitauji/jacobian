---
name: discover-math-capabilities
description: Derive evidence-backed additions and changes to Jacobian's mathematical capability portfolio from agent traces, evaluation results, datasets, research cases, and maintained mathematical backends. Use when asked what mathematical tools Jacobian should add, expand, split, consolidate, improve, or retire; when auditing proof or disproof workflows for capability gaps; when turning benchmark failures into capability proposals; or when researching new proof-assistant, CAS, solver, database, retrieval, construction, search, transformation, or verification integrations.
---

# Discover Math Capabilities

Turn observed mathematical work into capability, discovery, verification, and
evaluation decisions. Preserve agent-owned research strategy: recommend useful
mathematical operations and trust boundaries, not a preferred proof workflow.

## Establish the evidence

Declare the audit scope and inputs before proposing changes. Distinguish:

- agent traces, transcripts, tool calls, and user corrections;
- held-out evaluation outcomes and hidden-oracle judgments;
- public datasets and historical mathematical cases;
- the current capability catalog, descriptors, source, and tests;
- maintained external systems and their current documented contracts; and
- hypotheses unsupported by observed agent behavior.

Treat traces and evaluation failures as behavioral evidence. Treat datasets as
coverage opportunities. Treat papers, expert discussions, and public cases as
workflow evidence according to their artifact strength. Treat blogs, news,
social posts, and shared chats as leads, not proof of a result or a product
need.

When the request is research-only and contains no traces, produce capability
hypotheses with cheap discriminating evaluations. Do not present them as
measured gaps.

## Inspect Jacobian first

Read the repository's `AGENTS.md`, then consult the current product direction
and contracts as needed:

- `docs/explanation/goals.md`
- `docs/reference/tools.md`
- `docs/reference/capability-workflow-evaluations.md`

Inspect `capability://catalog`, `capability.describe`, source, and tests before
asserting that an operation is missing. Separate these failure classes:

- capability exists and works;
- capability exists but was unavailable, undiscoverable, or poorly described;
- capability was selected or parameterized poorly;
- capability lacks a required operation or contract field;
- validation, verification, or handoff is missing;
- environment, budget, or authorization prevented use; or
- mathematical reasoning is the bottleneck and no tool can replace it.

Prefer improving discovery, examples, errors, payloads, or batching when those
would fix the observed problem. Do not propose a new capability ID for every
friction event.

## Derive the mathematical operation

For each consequential event, identify the smallest agent-visible mathematical
outcome that would have changed it. Common moves include retrieving a premise,
constructing an object, computing an invariant, transforming a claim,
enumerating a finite family, searching for a witness, comparing candidates,
or checking a certificate. These are prompts for analysis, not a closed
taxonomy.

State the counterfactual precisely:

- input available at that point in the trace;
- output the capability would return;
- useful intermediate artifacts and relationships it must expose;
- measurable effect on correctness, false certification, runtime, tokens,
  calls, parameter errors, or reviewer confidence; and
- what the capability still could not decide or prove.

Cluster repeated instances by mathematical outcome, not by backend API call or
surface verb. Prefer specific domain-owned IDs such as
`graph.enumerate.nonisomorphic` over universal object, property, or solver
schemas. A capability may coordinate backend calls when they jointly produce
one coherent outcome, but it must preserve useful intermediate artifacts,
failures, relationships, scope, and obligations.

## Research existing systems

Before recommending custom mathematics, search for a maintained proof
assistant, CAS, solver, optimization system, mathematical database, or domain
library that already implements the operation. Verify current behavior against
official documentation, source, versions, and artifacts. Use generated
summaries only for discovery.

Prefer a thin pinned adapter when reproducibility, certificates, or semantics
depend on backend behavior. Reject mechanical wrappers for every backend
function. Record backend readiness, license or deployment constraints when
material, reproducibility requirements, and whether the backend emits a
replayable certificate.

## Define trust and contract boundaries

For each capability proposal, specify:

- one observable mathematical outcome and a namespaced ID;
- typed inputs, inline summary, and durable artifacts;
- exact or approximate behavior;
- bounded or exhaustive scope and completeness;
- deterministic or heuristic behavior;
- provider identity and pinned version where required;
- execution status, evidence type, assurance, and open obligations; and
- actionable invalid-input and parameter-error behavior.

Search, generation, retrieval, and computation produce evidence; they do not
verify themselves. For an exact conclusion, define an independent checker
bound to the exact claim, domain semantics, candidate, scope, certificate
format, and checker identity. If independent replay is unavailable, say what
assurance remains possible.

Do not gate experimental availability on evaluation. Contracts may be
version-breaking while experimental. Use evaluation evidence to guide
discovery, recommendation, defaults, consolidation, and retirement.

## Attach an evaluation

Pair each material proposal with a discriminating test. Prefer frozen tasks
with hidden versioned oracles and independently implemented replay. Include at
least one tempting incomplete, misbound, or semantically mismatched path.

For autonomous composition, compare the same model, budget, sampling
conditions, and tasks with and without the capability or family. Run multiple
repetitions when making comparative claims. Measure correctness, false
certification, runtime, tokens, calls, parameter errors, completion,
completeness, and evidence binding.

Prescribed-tool cases measure contract usability and conformance. They do not
establish portfolio value. Evaluate complete portfolios and targeted ablations
when deciding whether to keep, split, consolidate, rank, or retire
capabilities.

## Recommend a portfolio action

Rank actionable proposals by observed recurrence, mathematical leverage,
backend readiness, verifiability, and evaluation value. Do not rank by novelty
or by the number of possible datasets alone.

Choose one of:

- **add**: a missing atomic operation with a credible backend and evaluation;
- **expand**: an existing outcome needs more domain coverage or constraints;
- **split**: traces need independently useful intermediate outcomes;
- **consolidate**: separate IDs duplicate one mathematical outcome;
- **improve discovery**: the operation exists but agents cannot find or use it;
- **add verification**: useful evidence lacks independent replay;
- **evaluate**: evidence is promising but insufficient for a portfolio change;
- **defer**: reasoning, backend maturity, ownership, or verification is not
  ready; or
- **retire**: measured redundancy or harm outweighs demonstrated value.

Reject vague recommendations such as "better reasoning," opaque
`solve_conjecture` workflows, producer-certified evidence, generic universal
schemas, and proposals supported only by hindsight. A research hypothesis may
remain on the list when it includes its uncertainty and cheapest useful test.

## Report

Lead with the portfolio decision and the evidence that changed it. Include a
compact table with these fields:

| Evidence | Classification | Mathematical outcome | Existing support or gap | Proposed ID or change | Backend | Verification boundary | Evaluation | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

Then state:

- the strongest observed patterns and corrected misconceptions;
- capabilities already covering apparent gaps;
- prioritized changes with counterfactual benefits;
- research-only hypotheses, clearly separated;
- limitations and proof gaps; and
- issue-ready slices with observable success criteria when requested.

Use `audit-agent-workflow` for a detailed generic trace audit when available.
Use `design-agent-eval` when a finding has frozen inputs, a hidden oracle, a
plausible wrong path, and a measurable intervention. Use
`write-github-issue` only when the user asks to prepare or file issues, and do
not mutate external systems without authorization.
