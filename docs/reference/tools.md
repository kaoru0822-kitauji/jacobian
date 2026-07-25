# Tool surface

[Documentation home](../index.md)

- Status: v0.2 surface plus explicitly labeled provisional and planned tools
- Normative sources: [v0.2 specification](specifications/v0.2.md) and
  [conformance gate](conformance-v0.2.md)

Jacobian is a workbench of composable mathematical primitives. The generic
kernel understands artifacts, claims, candidates, predicates, witnesses,
certificates, reductions, budgets, and provenance. Mathematical meaning is
supplied by versioned domain plugins.

The model-facing surface is layered so adapters are easy to add and a
heuristic operation cannot masquerade as a verifier.

## Primitives, workflows, and adapters

The target primitive contract is a versioned capability with one observable
operation. It consumes typed artifacts and returns typed artifacts, explicit
relationships, new proof obligations when applicable, execution status,
assurance, and provenance. Agents and proof strategies compose primitives into
workflows without merging the assurance of their stages.

The current `CapabilityResult` has a typed operation-specific output and
artifact URIs but no generic first-class relationship or proof-obligation
fields. Until those fields are versioned, adapters must keep that information
inside their output schema. This is an active product-contract gap, not a
property callers should infer.

A capability adapter connects an external engine or domain operation to this
contract and registers it behind a capability ID. A domain plugin defines the
mathematical schemas, invariants, transformations, and witness meanings used by
that operation. An internal backend is an implementation detail used by an
adapter or plugin. None of these may authorize a checker; checker
authorization is an operator-controlled kernel action.

Some current lower-level MCP commands are composite compatibility workflows.
They remain documented because current clients use them, but new mathematical
operations should normally appear as capability IDs behind
`capability.describe` and `capability.invoke`.

## Capability-first MCP surface

The default local and remote profile advertises two tools:

| Tool | Capability |
| --- | --- |
| `capability.describe` | Read an installed capability's exact schema. `reference.solve` descriptions add domain predicate and candidate schemas, binding rules, and executable examples. |
| `capability.invoke` | Invoke an installed operation in `EXPLORE` or `VERIFY` mode. Inputs and outputs are validated against the selected descriptor. Completed reusable invocations create trust-labeled research episodes. |

Read `capability://catalog` to discover stable IDs, provider versions, supported
modes, compact JSON Schemas, and tags. Bundled IDs are `reference.solve`,
`lean.check`, and `knowledge.search`. Operator-installed adapters appear in the
same catalog without a new MCP tool. Tool-only clients should call
`capability.describe` before invoking an unfamiliar capability rather than
guessing payload fields.

Failed invocations carry stage-aware diagnostics with a stable code, JSON path
when available, schema URI when applicable, and a corrective hint. Invalid
requests, adapter failures, timeouts, and cancellations do not become research
episodes and never carry a mathematical conclusion.

`EXPLORE` returns heuristic or computed assurance and does not require a formal
claim or checker. `VERIFY` may promote a result only when it carries a valid
local verification record and the checked evidence. The `full` and
`verification` profiles retain the lower-level tools below for advanced
clients and compatibility.

## Core v0.2 operation tools

| Tool | Capability |
| --- | --- |
| `artifact.put` | Store an immutable, content-addressed candidate, claim, witness, certificate, program, or trace. Large content is returned through resource URIs. |
| `claim.validate` | Check that a formal problem specification is well-formed: schemas, domains, quantifiers, exact values, bounds, and referenced semantics. This does not establish correspondence with the informal conjecture. |
| `evaluate.batch` | Evaluate many candidates using a named problem plugin. Return objectives, proposed witnesses, arithmetic, coverage, evidence, and provenance. Evaluation never self-certifies. |
| `witness.find` | Attack a candidate by searching for a counter-witness or rescuing witness. Return a proposed witness, an exhausted-search certificate, or `UNKNOWN`. |
| `witness.verify` | Independently check that a witness is in-domain and has the claimed logical effect on the stated candidate or claim. |
| `shrink.run` | Reduce a candidate or witness while repeatedly invoking an authorized preservation checker. Report the achieved minimality class. |
| `certificate.verify` | Independently verify an exhaustive table, SAT/PB proof, LP dual, Farkas certificate, separator, interval proof, Lean proof term, or another registered certificate format. |

`evaluate.batch` is the central experimental interface.
`witness.verify` and `certificate.verify` are the public trust boundary.

## Current compatibility workflows

These workflows ship in the repository but are not additional v0.2 trust
boundaries or part of the frozen v0.2 conformance tool list:

| Tool | Composition |
| --- | --- |
| `lean.verify` | Used by the `lean.check` capability. It builds a claim-bound Lean certificate in the pinned `CORE` or `MATHLIB` environment, then replays it through `certificate.verify`. |
| `verification.run` | Composes artifact storage, claim validation, evaluation, witness search, and authorized witness replay for one bundled domain. Every stage retains its own assurance label. |

The local MCP adapter provides `capabilities`, `full`, and `verification`
projections. The compact verification projection omits unrelated research
tools and redundant output schemas. Its bootstrap resources project minimal
claim contracts and its composite workflow result projects only stage status,
assurance, evidence, and durable record URIs. Canonical registry schemas,
artifacts, tool semantics, and checker authority are unchanged.

`lean.check` is the capability ID used through `capability.invoke`;
`lean.verify` is the lower-level compatibility workflow. `lean.verify` never
accepts an import string or package path from a model.
`CORE` has no import and authorizes no axioms. `MATHLIB` has one
operator-pinned `Mathlib` import and an explicit standard trust-base allowlist;
the checker rejects any additional axiom reported by Lean.

`witness.find` may orchestrate verification and return `NONE_CERTIFIED`, but
only when the response references a `VERIFIED` record from
`certificate.verify`. Otherwise it returns an unverified exhausted-search
result or `UNKNOWN`.

## v0.2 representation tools

| Tool | Capability |
| --- | --- |
| `transform.apply` | Propose or compute a new representation, such as graph to path family, routing to polytope, recurrence to program, or formula to SAT/PB encoding. |
| `transform.verify` | Verify whether the transformation is an equivalence, over-approximation, under-approximation, or heuristic transformation, and check its proof obligation. |
| `polytope.separate` | For finite rational generator sets, perform exact coordinate projection and return either convex-combination weights or a strict separator. |

The component proposing a representation change cannot certify its own
relationship.

## Search tools

Search strategies share a typed experiment operation:

| Availability | Tool | Capability |
| --- | --- | --- |
| v0.2 | `search.enumerate` | Exhaustively enumerate a bounded candidate class using a domain-provided enumerator and auditable scope. |
| Provisional M3 | `search.run` | Run a typed proposer, evaluator, counterexample, refinement, and nomination loop as a durable experiment. |

These tools start experiment jobs and return experiment resource handles. They
do not produce verified conclusions by themselves. Exact enumeration, CEGIS,
constraint solving, parameter sweeps, beam or tree search, evolutionary search,
and agent-driven loops are strategies behind the common M3 orchestration
contract rather than separate kernel tools.

The resident MCP server returns `search.enumerate` and `search.run` handles
immediately. The local CLI waits for the bounded experiment and prints its
settled snapshot because a worker cannot outlive a short-lived CLI process.

## Optional domain tools

Domains expose only the operations they support:

| Tool | Example capability |
| --- | --- |
| `family.materialize` | Explicitly enumerate a complete bounded semantic family, such as all paths, legal deviations, generated words, or reachable states. |
| `family.compile` | Compile a large family into a BDD, ZDD, automaton, dynamic program, or oracle. |
| `structure.canonicalize` | Produce a canonical representation, automorphisms, and orbits for a supported finite structure. |

These are plugin capabilities, not mandatory universal tools. A numerical
analysis plugin need not implement graph canonicalization; a Lean proof plugin
need not implement mutation.

## Claim-transformation and corpus operations

The provisional implementation exposes several named workflow façades. Their
stage outputs are hypotheses or research records unless separately verified:

| Milestone | Tool | Capability |
| --- | --- | --- |
| Provisional M4 | `conjecture.repair` | Propose nearby claims after a counterexample by changing assumptions, constants, domains, or conclusions. |
| Provisional M4 | `conjecture.generate` | Compatibility workflow that generates candidate statements, deduplicates them, requests bounded falsification, and ranks survivors while retaining stage evidence. |
| Provisional M4 | `parameter.generalize` | Propose parameter regions around a verified construction and preserve proposed or sampled evidence labels. |
| Provisional M4 | `parameter.region.promote` | Replay an authorized certificate bound to an immutable region subject before labeling it verified sufficient or necessary. |
| Current product track | `knowledge.search` capability ID | Query locally indexed capability episodes through `capability.invoke` while preserving each record's assurance. |
| M5 | provider-backed `knowledge.search` | Extend local retrieval with cross-project records, temporal cutoffs, review, and retraction. |
| M5 | `abstraction.extract` | Suggest an abstract mathematical explanation for supplied or retrieved artifacts. |
| M5 | `episode.compare` | Compare failures and propose recurring obstructions or no-go lemmas. |
| M5 | `certificate.simplify` | Minimize a certificate while replaying its authorized checker locally. |

The M4 workflows operate without a shared corpus. Their intended primitive
operations are claim derivation, deduplication, scoring, bounded falsification,
and parameter analysis; agents may compose them differently from the bundled
façades. When no M5 provider is
configured, they deduplicate against supplied or local experiment records and
report corpus-wide novelty as unknown. Corpus retrieval can suggest inputs to
any tool but cannot authorize checkers or promote verification status.
The three hypothesis-producing M4 tools share one `HypothesisTransformer`
plugin operation and may route their outputs through `search.run`; Jacobian
does not embed a conjecture grammar or synthesis framework.
`parameter.region.promote` is a kernel verification operation, not a fourth
plugin transformation. Sample artifacts must enter through explicit workflow
evidence before a plugin may cite them in a sampled parameter region.

## Internal backends

The initial public API does not include generic `solver.solve` or `sandbox.run`
tools.

SAT, SMT, LP, MIP, SyGuS, interval arithmetic, and Lean use typed internal
adapters with distinct inputs, outputs, and certificate formats. Sandboxed
execution is infrastructure used by later search tools, not a mathematical
truth primitive.

## Resources, not tools

Read-only discovery and large-object access use MCP resources:

```text
artifact://sha256/<digest>
capability://catalog
reference://catalog
experiment://<id>
experiment://<id>/accounting
experiment://<id>/scope
experiment://<id>/archive
```

Schemas, semantics, plugin manifests, witnesses, certificates, and verification
records are all ordinary artifacts and use the artifact resource template.
`reference://catalog` exposes the identifiers installed by the bundled
reference fixtures. Checker administration remains outside the model-facing
MCP surface.

Experiment resources expose durable snapshots and compact artifact handles.
`experiment.cancel`, `experiment.pause`, and `experiment.resume` change
provisional M3 strategy-search state. Pause takes effect at a committed
checkpoint; resume continues the same invocation and lineage.

## Operator actions, not model tools

The following are administrative CLI or service operations:

```text
plugin install, enable, or remove
checker authorize or revoke
storage garbage collection
schema publication
conformance-suite execution
retention-policy changes
```

An untrusted model or problem plugin must not be able to authorize a checker or
change retention and trust policy through the mathematical MCP surface.

## Later reproducibility workflows

v1.0 may expose:

| Tool | Capability |
| --- | --- |
| `bundle.export` | Assemble a content-addressed, independently replayable result bundle. |
| `bundle.verify` | Check bundle integrity, resolve its authorized checkers, and replay its verification records. |

These are workflows over existing artifacts and verification tools, not new
sources of mathematical truth.
