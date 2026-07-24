# Tool surface

[Documentation home](../index.md)

- Status: v0.2 surface plus explicitly labeled provisional and planned tools
- Normative sources: [v0.2 specification](specifications/v0.2.md) and
  [conformance gate](conformance-v0.2.md)

Jacobian is a general research kernel. Its core tools understand artifacts,
claims, candidates, predicates, witnesses, certificates, reductions, budgets,
and provenance. Mathematical meaning is supplied by versioned domain plugins.

The public tool surface is layered so a heuristic operation cannot masquerade
as a verifier.

## Core v0.2 tools

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

## Conjecture and corpus tools

These tools produce hypotheses or research records unless their outputs are
separately verified:

| Milestone | Tool | Capability |
| --- | --- | --- |
| Provisional M4 | `conjecture.repair` | Propose nearby claims after a counterexample by changing assumptions, constants, domains, or conclusions. |
| Provisional M4 | `conjecture.generate` | Generate, deduplicate, falsify, and rank candidate statements. |
| Provisional M4 | `parameter.generalize` | Propose parameter regions around a verified construction and preserve proposed or sampled evidence labels. |
| Provisional M4 | `parameter.region.promote` | Replay an authorized certificate bound to an immutable region subject before labeling it verified sufficient or necessary. |
| M5 | `memory.search` | Ask an optional corpus provider for prior experiments, failures, witnesses, certificates, and research episodes with trust labels. |
| M5 | `abstraction.extract` | Suggest an abstract mathematical explanation for supplied or retrieved artifacts. |
| M5 | `episode.compare` | Compare failures and propose recurring obstructions or no-go lemmas. |
| M5 | `certificate.simplify` | Minimize a certificate while replaying its authorized checker locally. |

The M4 tools operate without a shared corpus. When no M5 provider is
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
