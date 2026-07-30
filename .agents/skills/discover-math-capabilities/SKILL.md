---
name: discover-math-capabilities
description: Mine row-level mathematical datasets, known solutions, formal artifacts, research cases, agent traces, and maintained backends for recurring mathematical moves that justify additions or changes to Jacobian's capability portfolio. Use when asked what mathematical tools Jacobian should add, expand, split, consolidate, improve, or retire; when extracting tool ideas from proofs, counterexamples, transcripts, datasets, or failed attempts; or when turning public cases into typed capability proposals and reproduction cases. This skill performs open workflow mining with answers visible; hand accepted implementation-ready candidates to implement-math-capability and use evaluate-math-capabilities for held-out comparative evaluation.
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

## Inspect rows and primary artifacts

Use landing pages, indexes, social posts, and dataset cards to map the source
bundle, not as substitutes for its mathematical contents. Inspect enough
primary examples to see variation across:

- successful proofs, counterexamples, constructions, and formal checks;
- failed attempts, false premises, rejected proofs, and reviewer corrections;
- easy and hard cases, domains, labels, and source families; and
- natural-language, executable, and machine-checkable artifacts.

For datasets, inspect the schema and identifiable rows at a pinned revision.
For repositories and pull requests, inspect the exact statement, decisive
object or proof, computation, checker, and review corrections. For transcripts,
extract tool-visible actions, artifacts, failures, and user corrections; do not
treat hidden reasoning or persuasive narration as mathematical evidence. Follow
papers, forums, blogs, and social claims to their primary objects before
crediting a method.

Keep downloaded corpora, source-bundle inventories, scratch ledgers, and dated
investigations in temporary or ignored storage unless a durable research record
is explicitly requested. Commit generalized process guidance, stable
reproduction fixtures, benchmark cases, contracts, and implementation—not a
one-off URL inventory.

When a public case is ready for reproducible agent evaluation, hand its frozen
statement, provenance, contamination class, expected mathematical outcome, and
independent checking boundary to `evaluate-math-capabilities` and the local
`harbor-benchmarks` skill. Discovery does not own Harbor task packaging, task
digests, Oracle execution, or model-comparison claims.

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
move ledger:

| Case or row | Inputs before move | Mathematical operation | Output or artifact | Downstream use | Failure or alternative | Verification |
| --- | --- | --- | --- | --- | --- | --- |

Treat each consequential transition as a move episode:

```text
available mathematical state
→ operation performed
→ inspectable mathematical output
→ changed downstream decision
→ independent check, open obligation, or failure
```

Do not summarize a whole proof or transcript as one move. Split exact
evaluation, transformation, construction, search, comparison, reduction, and
replay when their outputs remain independently useful to an agent.

Identify the smallest agent-visible mathematical outcome that would have
changed a consequential step. Examples include retrieving a premise,
constructing an object, computing an invariant, transforming a claim,
enumerating a finite family, finding a witness, comparing candidates, or
checking a certificate. These are prompts, not a closed taxonomy.

For each proposed outcome, state:

- the exact supporting episodes and source locators;
- the input available at that point;
- the typed output and inline summary;
- durable intermediate artifacts and relationships;
- exactness, scope, completeness, and determinism;
- the provider and version requirements;
- the independent verification boundary; and
- the counterfactual reason the outcome would help an agent; and
- what the operation still cannot establish.

Cluster repeated moves by mathematical outcome, not by dataset name or backend
API call. Prefer domain-owned IDs such as `graph.enumerate.nonisomorphic` or
`polynomial.compute.groebner_basis` over universal object or solver schemas.
Normally require the move to recur in at least two independent cases or source
families. Admit a single-source exception only for a fundamental primitive with
clear reuse, a maintained backend, and a strong verification boundary.

Distinguish a missing operation from a strategy gap. If current capabilities
already expose the necessary intermediate outcomes, improve discovery,
descriptors, examples, or a reusable agent skill instead of adding another
capability.

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

## Apply the candidate gate

Create a candidate record before implementation using the
[shared handoff format](../../../docs/reference/capability-development-handoffs.md).
Set `stage=discovery` and record the gate status, evidence references, open
obligations, and next action.

| Gate | Required evidence |
| --- | --- |
| Recurrence | Independent move episodes or a justified fundamental-primitive exception |
| Leverage | The output changes a consequential downstream mathematical decision |
| Atomicity | One coherent agent-visible outcome with useful intermediate artifacts |
| Portfolio fit | A real gap, split, consolidation, or improvement rather than a duplicate |
| Backend readiness | Maintained implementation, versioning, deployment, and license understood |
| Contract honesty | Typed input/output with explicit exactness, scope, completeness, and determinism |
| Trust boundary | Independent replay path or an explicit unverified obligation |
| Reproduction | At least one primary public case can exercise the proposed contract |
| Evaluation hypothesis | A held-out comparison could distinguish value from persuasive replay |

Reject or defer candidates that are dataset-specific wrappers, opaque
multi-stage workflows, mechanical backend-function mirrors, answer generators,
self-verifying searches, or operations whose failure state could be mistaken
for a theorem. Record the failed gate and evidence; a rejection ledger prevents
the same weak idea from being repeatedly rediscovered.

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

## Hand off implementation-ready candidates

Hand an accepted candidate to `implement-math-capability` only when the
candidate gate is complete enough to freeze an experimental contract. Use the
[shared handoff format](../../../docs/reference/capability-development-handoffs.md)
with `stage=discovery,status=accepted`; the stage-specific record must cover
the outcome and ID, move episodes, portfolio delta, contract and failure
semantics, runtime snapshot, assurance obligations, reproductions, and
evaluation hypothesis.

Discovery does not authorize implementation to broaden the scope, add nearby
backend functions, or promote the result to `VERIFIED`. If the candidate needs
an independent verification path after its producer contract is stable, use
`implement-math-capability-checker`.

## Hand off comparative questions

When the proposal is concrete enough to ask whether it improves autonomous
performance, hand it to `evaluate-math-capabilities` using the same record.
Include the counterfactual benefit, public and adversarial cases, proposed
control ablation, checker boundary, contamination notes, and discriminating
metrics. Do not construct hidden oracles during open workflow mining unless the
user also asks for an evaluation.

## Report

Lead with the repeated process evidence and the resulting portfolio decisions.
Use a compact table:

| Evidence | Mathematical move | Current support or gap | Proposed change | Backend | Verification boundary | Public reproduction | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |

Separate:

- capabilities already covering apparent gaps;
- additions, expansions, splits, consolidation, or retirement;
- research-only hypotheses;
- rejected candidates and the gates they failed;
- limitations and unresolved proof gaps; and
- proposals ready for comparative evaluation.

Continue until the remaining ideas lack repeated workflow evidence, meaningful
leverage, agent-visible atomicity, backend readiness, an honest contract,
trustworthy verification boundaries, portfolio distinctness, or a testable
value hypothesis. “No more good candidates” is a supported portfolio decision,
not a requirement to manufacture another capability.
