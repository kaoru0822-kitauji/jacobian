# Capability surface

[Documentation home](../index.md)

- Status: v0.2 alpha; capability contracts are pre-stable
- Normative sources: [v0.2 specification](specifications/v0.2.md) and
  [conformance gate](conformance-v0.2.md)

Jacobian exposes mathematical operations as namespaced capabilities. The
model-facing MCP surface is deliberately small:

| MCP tool | Purpose |
| --- | --- |
| `capability.describe` | Read an installed capability's descriptor and exact input and output schemas. |
| `capability.invoke` | Invoke an installed capability in `EXPLORE` or `VERIFY` mode. |

Read `capability://catalog` to discover installed capability IDs, provider
versions, supported modes, compact schemas, and tags. Catalog membership means
that an operation is installed and invocable. It does not imply compatibility
support, recommendation, conformance coverage, or authority to return
`VERIFIED`.

There are no alternate MCP tool profiles and no public top-level MCP commands
for individual mathematical operations. Adding a capability does not add a
new MCP tool.

## Capability contract

Each capability has one agent-visible mathematical outcome. It consumes typed
inputs and returns a typed result with:

- execution status and operation-specific output;
- artifact references and relationships;
- scope and completeness;
- exact, approximate, bounded, exhaustive, deterministic, or heuristic
  qualifiers as applicable;
- assurance and any remaining proof obligations;
- provider and execution provenance.

Backend-call atomicity is not required. An adapter may coordinate several
backend calls when they jointly implement one coherent operation, but it must
not hide mathematically useful intermediate artifacts, failures, relationships,
or obligations.

`EXPLORE` returns proposed, heuristic, or computed evidence. `VERIFY` may
return `VERIFIED` only when an operator-authorized independent checker accepts
evidence bound to the exact claim, semantics, candidate, scope, certificate
format, and checker version. Search, generation, evaluation, and computation
cannot certify their own conclusions.

Invalid requests, adapter failures, timeouts, and cancellations return
stage-aware diagnostics. They do not become mathematical conclusions.
Domain adapters validate their complete Pydantic request model before
computation or artifact writes. JSON Schema remains the discovery contract;
Pydantic enforces cross-field conditions such as polynomial-map dimensions,
finite operation-table closure, and bounded exact encodings.

## Installed bundled capabilities

The base installation currently includes these kernel capability IDs:

| Capability ID | Outcome |
| --- | --- |
| `artifact.put` | Materialize one immutable, content-addressed artifact. |
| `claim.validate` | Validate one formal claim against installed schemas and domain semantics without asserting its truth. |
| `evaluate.batch` | Evaluate a batch of candidates and return computed evidence without self-certification. |
| `witness.find` | Search for one claim-bound witness or return an explicitly bounded non-conclusion. |
| `witness.verify` | Independently replay the claimed logical effect of one witness. |
| `certificate.verify` | Independently replay one registered certificate format. |
| `shrink.run` | Reduce one candidate or witness while preserving a checker-backed property. |
| `structure.canonicalize` | Produce one implementation-bound canonical representation of a supported structure. |
| `search.enumerate` | Start one bounded enumeration with explicit scope and accounting. |
| `experiment.inspect` | Read one experiment snapshot. |
| `experiment.wait` | Wait for one experiment to settle within the declared bound. |
| `experiment.cancel` | Request cancellation of one experiment. |
| `transform.apply` | Produce one proposed representation or claim transformation and its obligations. |
| `transform.verify` | Independently check one proposed transformation relationship. |
| `polytope.separate` | Compute one exact finite rational convex-hull witness or separator. |
| `parameter.region.promote` | Check one immutable parameter-region subject with an authorized certificate. |
| `case.partition.finite` | Partition an explicit finite domain and report exact coverage. |
| `graph.search.atlas` | Search the bounded Graph Atlas and return matching graph candidates with explicit coverage limits. |
| `graph.compute.properties` | Compute supported exact invariants of an explicit graph. |
| `graph.compute.neighborhood_independence` | Compute every open-neighborhood independence optimum, witness, sum, and exact rational average. |
| `polynomial.map.evaluate` | Evaluate one sparse rational polynomial map at one exact rational point. |
| `polynomial.map.compute_jacobian` | Compute an exact Jacobian matrix and determinant for one sparse rational polynomial map. |
| `polynomial.map.collision_witness` | Compare two exact point-evaluation artifacts and materialize a candidate collision witness. |
| `universal_algebra.evaluate_laws` | Exhaust finite magma laws or return the first canonical failing valuation. |
| `universal_algebra.search.countermodel` | Search all operation tables of one bounded carrier order for a source-law model falsifying a target law. |
| `knowledge.search` | Retrieve locally indexed capability episodes without changing their assurance. |

`polynomial.map.evaluate` is the sole bundled operation that computes a point
image. `polynomial.map.collision_witness` accepts two evaluation artifact URIs
for the same map, compares their declared canonical rational values, and
exposes any resulting candidate witness for independent replay. It does not
recompute or certify either evaluation. This keeps evaluation and witness
construction separate while making their composition explicit to the agent.

When the operator enables bundled references, the catalog also includes:

| Capability ID | Outcome |
| --- | --- |
| `lean.check` | Check a Lean proof in an operator-pinned environment and return its replay evidence. |

Operator-installed adapters appear in the same catalog. Agents should call
`capability.describe` before invoking an unfamiliar capability instead of
guessing payload fields.

## Mathematical operation portfolio

The portfolio may include capabilities for operations such as:

- artifact materialization;
- claim validation;
- candidate evaluation;
- witness search and independent witness checking;
- certificate replay;
- bounded enumeration and canonicalization;
- exact invariant computation;
- representation and claim transformation;
- finite-family materialization;
- premise and research-record retrieval;
- proof-assistant checking;
- exact separation, constraint solving, or construction.

These are capability families, not a required taxonomy. Use domain-specific
IDs and contracts where mathematical semantics differ. For example,
`graph.enumerate.nonisomorphic` and
`polynomial.compute.groebner_basis` should not be forced through a universal
object or solver schema.

Useful low-level operations may retain descriptive IDs such as
`claim.validate`, `witness.find`, `witness.verify`, or
`certificate.verify`. Those names identify capabilities invoked through
`capability.invoke`; they are not separate MCP tools.

Opaque multi-stage commands are not part of the public surface. Agents and
skills should compose generation, evaluation, ranking, falsification,
refinement, and verification from separately invocable capabilities. An
optional workflow capability is appropriate only when it has one coherent
mathematical outcome and preserves visible intermediate artifacts and
assurance boundaries.

## Adapters and trust boundaries

Capability adapters connect maintained proof assistants, CAS systems, solvers,
mathematical databases, and domain libraries to the common contract. Domain
plugins own mathematical schemas, transformations, invariant meanings, and
required checker roles. The kernel owns artifact identity, budgets, execution
status, provenance, assurance, and checker authorization.

SAT, SMT, LP, MIP, SyGuS, interval arithmetic, and proof assistants should use
typed domain adapters with explicit certificate formats. Jacobian does not
expose a generic `solver.solve` or `sandbox.run` truth primitive.

An adapter or plugin cannot authorize its own checker. Checker administration
is operator-controlled and outside the model-facing MCP surface.

## Resources

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

Only resource templates implemented by the installed kernel are advertised.
Schemas, semantics, plugin manifests, witnesses, certificates, and
verification records are ordinary artifacts. Resource access does not alter
their assurance.
