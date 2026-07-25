---
name: discover-math-capabilities
description: Mine mathematical datasets, known solutions, formal artifacts, research cases, agent traces, and maintained backends to identify evidence-backed additions or changes to Jacobian's capability portfolio. Use when asked what mathematical tools Jacobian should add, expand, split, consolidate, improve, or retire; when auditing proof or disproof processes for recurring mathematical operations; or when turning public cases and workflow traces into capability proposals and reproduction cases. This skill performs open workflow mining with answers visible; use evaluate-math-capabilities for held-out comparative evaluation.
---

# Discover Math Capabilities

Determine what Jacobian should expose by reconstructing mathematical work from
source evidence. Keep answers, successful methods, failures, and review
artifacts visible during discovery. The objective is to find reusable
mathematical operations and trust boundaries, not to measure autonomous model
performance.

## Establish the source bundle

Declare the scope and inputs before proposing changes. Distinguish:

- problem statements, known solutions, counterexamples, and formal proofs;
- agent transcripts, tool calls, failed attempts, and user corrections;
- public datasets and historical mathematical cases;
- the current capability catalog, source, descriptors, and tests;
- maintained external systems and their documented contracts; and
- hypotheses unsupported by repeated workflow evidence.

Treat machine-checkable proofs, replayable certificates, and explicit objects
as the strongest process evidence. Treat expert discussions and curated
databases as useful context. Treat blogs, news, social posts, and shared chats
as leads until their primary artifacts are inspected.

Record dataset revision, license, redistribution constraints, and contamination
risk when material. Do not copy a large dataset into the repository merely to
mine it.

## Inspect Jacobian first

Read `AGENTS.md`, then consult these files as needed:

- `docs/explanation/goals.md`
- `docs/reference/tools.md`
- `docs/reference/capability-workflow-evaluations.md`

Inspect `capability://catalog`, `capability.describe`, source, and tests before
calling an operation missing. Classify each observed problem as one of:

- capability exists and works;
- capability exists but was unavailable or hard to discover;
- capability was selected or parameterized poorly;
- capability lacks a needed operation or contract field;
- verification or artifact handoff is missing;
- environment, budget, or authorization prevented use; or
- mathematical reasoning, rather than tooling, was the bottleneck.

Prefer better examples, errors, payloads, batching, or discovery when those
address the observed problem. Do not create a new ID for every backend function
or friction event.

## Reconstruct the mathematical process

For each representative case, inspect the statement, successful resolution,
failed routes, intermediate artifacts, and verification method. Build a compact
workflow ledger:

| Task | Successful moves | Failed moves | External systems | Useful artifacts | Verification | Capability implication |
| --- | --- | --- | --- | --- | --- | --- |

Identify the smallest agent-visible mathematical outcome that would have
changed a consequential step. Examples include retrieving a premise,
constructing an object, computing an invariant, transforming a claim,
enumerating a finite family, finding a witness, comparing candidates, or
checking a certificate. These are prompts, not a closed taxonomy.

For each proposed outcome, state:

- the input available at that point;
- the typed output and inline summary;
- durable intermediate artifacts and relationships;
- exactness, scope, completeness, and determinism;
- the provider and version requirements;
- the independent verification boundary; and
- what the operation still cannot establish.

Cluster repeated moves by mathematical outcome, not by dataset name or backend
API call. Prefer domain-owned IDs such as `graph.enumerate.nonisomorphic` or
`polynomial.compute.groebner_basis` over universal object or solver schemas.

## Research existing systems

Before recommending custom mathematics, inspect maintained proof assistants,
CAS systems, solvers, optimization tools, databases, and domain libraries that
already implement the outcome. Verify behavior against current source and
official documentation. Prefer a thin pinned adapter over reimplementation.

Record backend readiness, deployment and license constraints, reproducibility
requirements, and whether it emits a replayable certificate. Search,
retrieval, generation, and computation produce evidence; they do not verify
their own conclusions.

## Define the trust boundary

For exact conclusions, identify an independent checker bound to the exact
claim, domain semantics, candidate, scope, certificate format, and checker
identity. If independent replay is unavailable, label the attainable assurance
and open obligation instead of treating provider output as verified.

Preserve useful intermediate objects, failures, transformations, and
obligations. Do not replace them with an opaque `solve_conjecture` workflow.
Agent-visible mathematical atomicity matters; backend-call atomicity does not.

## Reproduce known cases

Use a small selection of public cases to test whether a proposed contract can
reproduce known work:

- the capability accepts the available source artifacts;
- its output exposes the mathematically useful intermediate state;
- scope and completeness are truthful;
- failures remain non-conclusions; and
- independent replay works when claimed.

These are public reproduction and regression cases. They show contract fitness,
not general portfolio value. Do not call a capability beneficial merely because
it replays the examples that inspired it.

## Hand off comparative questions

When the proposal is concrete enough to ask whether it improves autonomous
performance, hand it to `evaluate-math-capabilities`. Supply:

- the capability hypothesis and counterfactual benefit;
- public reproduction cases;
- plausible wrong paths and false-certification risks;
- candidate backends and checker boundaries;
- applicable datasets and contamination notes; and
- the metrics that could distinguish success from a persuasive replay.

Do not construct hidden oracles during open workflow mining unless the user also
asks for an evaluation.

## Report

Lead with the repeated process evidence and the resulting portfolio decisions.
Use a compact table:

| Evidence | Mathematical move | Current support or gap | Proposed change | Backend | Verification boundary | Public reproduction | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |

Separate:

- capabilities already covering apparent gaps;
- additions, expansions, splits, consolidation, or retirement;
- research-only hypotheses;
- limitations and unresolved proof gaps; and
- proposals ready for comparative evaluation.
