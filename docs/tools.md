# Tool surface

Jacobian is a general research kernel. Its core tools understand artifacts,
claims, candidates, predicates, witnesses, certificates, reductions, budgets,
and provenance. Mathematical meaning is supplied by versioned domain plugins.

The public tool surface is layered so a heuristic operation cannot masquerade
as a verifier.

## v0.1 core tools

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

The component proposing a representation change cannot certify its own
relationship.

## Search tools

Search strategies have separate typed operations:

| Release | Tool | Capability |
| --- | --- | --- |
| v0.2 | `search.enumerate` | Exhaustively enumerate a bounded candidate class using a domain-provided enumerator and auditable scope. |
| v0.3 | `search.evolve` | Run evolutionary or program search with Pareto archives, novelty, lineage, and periodic verification. |
| v0.3 | `search.cegis` | Alternate candidate synthesis, verified counter-witnesses, and refinement constraints. |
| v0.3 | `search.tree` | Run beam, best-first, Monte Carlo tree, or related state-space search. |

These tools start experiment jobs and return experiment resource handles. They
do not produce verified conclusions by themselves.

## Optional domain tools

Domains expose only the operations they support:

| Tool | Example capability |
| --- | --- |
| `family.materialize` | Explicitly enumerate a complete bounded semantic family, such as all paths, legal deviations, generated words, or reachable states. |
| `family.compile` | Compile a large family into a BDD, ZDD, automaton, dynamic program, or oracle. |
| `structure.canonicalize` | Produce a canonical representation, automorphisms, and orbits for a supported finite structure. |
| `polytope.separate` | Perform typed exact projection, convex-hull membership, separation, and facet computation. |

These are plugin capabilities, not mandatory universal tools. A numerical
analysis plugin need not implement graph canonicalization; a Lean proof plugin
need not implement mutation.

## Research tools

These tools produce hypotheses or research records unless their outputs are
separately verified:

| Release | Tool | Capability |
| --- | --- | --- |
| v0.4 | `memory.search` | Retrieve prior experiments, failures, witnesses, certificates, and research episodes with trust labels. |
| v0.4 | `abstraction.extract` | Suggest an abstract mathematical explanation for concrete artifacts. |
| v0.4 | `episode.compare` | Compare failures and propose recurring obstructions or no-go lemmas. |
| v0.4 | `certificate.simplify` | Minimize a certificate while replaying its authorized checker. |
| v0.5 | `conjecture.repair` | Propose nearby claims after a counterexample by changing assumptions, constants, domains, or conclusions. |
| v0.5 | `conjecture.generate` | Generate, deduplicate, falsify, and rank candidate statements. |
| v0.5 | `parameter.generalize` | Propose and certify parameter regions around a verified construction. |

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
schema://sha256/<digest>
plugin://sha256/<digest>
checker://sha256/<digest>
experiment://<opaque-id>
```

Consequently, v0.1 does not need `artifact.get`, `schema.get`, `plugin.list`, or
`checker.list` tools. Clients read those resources and use MCP's ordinary tool
discovery for installed public operations.

Experiment status is also a resource. State-changing lifecycle actions such as
`experiment.cancel`, `experiment.pause`, and `experiment.resume` remain tools.

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
