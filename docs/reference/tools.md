# Capability surface

[Documentation home](../index.md)

- Status: v0.2 alpha; capability contracts are pre-stable
- Normative sources: [v0.2 specification](specifications/v0.2.md) and
  [conformance gate](conformance-v0.2.md)

Jacobian exposes mathematical operations as namespaced capabilities and
operational working state through three direct workspace tools. The
model-facing MCP surface contains five tools:

| MCP tool | Purpose |
| --- | --- |
| `capability.describe` | Read an installed capability's descriptor and exact input and output schemas. |
| `capability.invoke` | Invoke an installed capability in `EXPLORE` or `VERIFY` mode. |
| `workspace.open` | Create one durable agent workspace, canonical problem card, pinned `main` branch, and immutable initial revision. |
| `workspace.write` | Append scratch, findings, attempts, lifecycle marks, and focus against an exact base revision. |
| `workspace.query` | Read a deterministic `RESUME`, `FRONTIER`, `ATTEMPTS`, `CONTEXT`, or `STALE` view. |

Read `capability://catalog` to discover installed capability IDs, provider
versions, supported modes, compact schemas, and tags. Catalog membership means
that an operation is installed and invocable. It does not imply compatibility
support, recommendation, conformance coverage, or authority to return
`VERIFIED`.

There are no alternate MCP tool profiles and no public top-level MCP commands
for individual mathematical operations. Adding a capability does not add a
new MCP tool. Workspace tools are an explicit operational-state exception:
successful persistence has no mathematical assurance level.

## Epistemic workspace

`workspace.open` creates exactly one canonical problem card. Only
`workspace.open` may create that card. Every later mutation carries an
idempotency key; `workspace.write` advances the branch only when
`base_revision` is still its current head. Full accepted batches are available
through the returned immutable `revision_artifact_uri`.

Within a write, entries use unique `client_ref` values. Findings record a
`kind`, `title`, `body`, and optional explicit dependency or assumption
references. Attempts record a target, method, operational outcome, and summary.
`OPEN_GOAL` normalizes to `GOAL`; `SUCCEEDED` normalizes to `COMPLETED`.
Completion never means `VERIFIED` and never closes a goal automatically.

Append-only margin marks record paper-like lifecycle state:

- `ACTIVE` explicitly reopens or restores a card;
- `CLOSED` closes a `GOAL` or `OPEN_QUESTION` as workflow state;
- `RETRACTED` withdraws a card and invalidates explicit dependents;
- `SUPERSEDED` names a replacement and invalidates old dependents;
- `ARCHIVED` files a card without invalidating dependents.

Every mark requires `reason`; the unambiguous `summary` input alias normalizes
to it. A `RETRACTED` or `SUPERSEDED` card must be explicitly restored with
`ACTIVE` before `CLOSED` or `ARCHIVED` can clear its invalidating state.
Supersession does not prove equivalence or reconnect dependents.

Workspace drafts cannot set `verification`, `assertion`, or derived `stale`.
Findings, attempts, marks, focus, and retrieval remain `AGENT_RECORDED` and
`UNVERIFIED`. Stale warnings follow only current `RETRACTED` or `SUPERSEDED`
roots through explicit dependency and assumption links; absence of a warning
says nothing about truth or semantic completeness.

`workspace.query` optionally accepts an exact expected `revision_id`.
`CONTEXT` additionally requires `target_card_id` and returns a bounded,
dependency-first closure plus recent target attempts. It reports
`total_dependency_count` and `truncated`; it does not infer relevance or
missing premises. Active stale goals remain visible until an explicit
`CLOSED`, `ARCHIVED`, `RETRACTED`, or `SUPERSEDED` mark changes their workflow
state.

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

Installed descriptors expose the exact provider version, digest kind and
digest, platform, install tier, license metadata, detected features, and fixed
checker identities. Results repeat the selected provider and provider digest.
The [provider runtime contract](provider-runtime.md) defines health probing,
fail-closed registration, and repeatable local measurement.

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
| `graph.realize.degree_sequence` | Construct a simple graph with an exact degree sequence, or return a replayable Erdős–Gallai/basic obstruction. |
| `graph.compute.properties` | Compute supported exact invariants of an explicit graph. |
| `graph.compute.neighborhood_independence` | Compute every open-neighborhood independence optimum, witness, sum, and exact rational average. |
| `graph.isomorphism.verify` | Independently verify one explicit vertex bijection between two existing graph artifacts by exhaustive adjacency and nonadjacency replay. |
| `polynomial.map.evaluate` | Evaluate one sparse rational polynomial map at one exact rational point. |
| `polynomial.map.compute_jacobian` | Compute an exact Jacobian matrix and determinant for one sparse rational polynomial map. |
| `polynomial.map.collision_witness` | Compare two exact point-evaluation artifacts and materialize a candidate collision witness. |
| `polynomial.identity.verify` | Independently verify equality or inequality of two sparse polynomials over one declared rational polynomial ring. |
| `polynomial.map.collision.search` | Search one fully declared finite rational grid for the first exact collision with reconciled point accounting. |
| `polynomial.factor.compute` | Factor one univariate polynomial over QQ and materialize its exact reconstructed product without self-certifying irreducibility. |
| `matrix.determinant.compute` | Compute the exact determinant of one square rational matrix and materialize the result. |
| `matrix.rank.compute` | Compute the exact rank and pivot columns of one rectangular rational matrix. |
| `polynomial.system.solution.verify` | Independently check one exact rational assignment against every equation and inequation in a finite polynomial system. |
| `universal_algebra.evaluate_laws` | Exhaust finite magma laws or return the first canonical failing valuation. |
| `universal_algebra.search.countermodel` | Search all operation tables of one bounded carrier order for a source-law model falsifying a target law. |
| `knowledge.search` | Retrieve locally indexed capability episodes without changing their assurance. |

`polynomial.map.evaluate` is the sole bundled operation that computes a point
image. `polynomial.map.collision_witness` accepts two evaluation artifact URIs
for the same map, compares their declared canonical rational values, and
exposes any resulting candidate witness for independent replay. It does not
recompute or certify either evaluation. This keeps evaluation and witness
construction separate while making their composition explicit to the agent.

`matrix.determinant.compute` and `matrix.rank.compute` use deterministic exact
rational arithmetic and return `COMPUTED` assurance. Their result artifacts
remain unverified: a future independently implemented and operator-authorized
checker must replay a determinant or rank claim before Jacobian may report
`VERIFIED`.

Optional exact runtimes add narrowly scoped operations only when their pinned
provider identity is available:

| Capability ID | Availability and outcome |
| --- | --- |
| `sat.model.find` | With CaDiCaL 3.0.1, preserve one total assignment candidate without certifying SAT. |
| `sat.unsat_proof.find` | With CaDiCaL 3.0.1, preserve raw DRAT evidence without certifying UNSAT. |
| `smt.unsat_proof.find` | With the `smt` extra and cvc5 1.3.4, preserve raw Alethe for one pinned-profile QF query, expose holes, and retain `UNKNOWN`. |
| `linear.rational_solution.find` | With the `flint` extra and Python-FLINT 0.9.0, produce one exact rational vector for a declared `A x = b` system; not-found remains a non-conclusion. |
| `matrix.normal_form.hermite` | With the `flint` extra and Python-FLINT 0.9.0, produce exact `H` and `U` for the proposed row-HNF relation `H = U A`; the provider does not verify the relation or form. |

See the [SAT artifact contracts](sat-artifacts.md) and
[SMT Alethe artifact contracts](smt-artifacts.md), and
[exact rational solution artifacts](linear-rational-solutions.md) and
[integer matrix Hermite normal form](matrix-hermite-normal-form.md) for exact
input profiles, resource bounds, artifact bindings, and independent
verification boundaries.

When the operator enables bundled references, the catalog also includes:

| Capability ID | Outcome |
| --- | --- |
| `lean.declaration.search` | Search public declarations by a bounded name and/or elaborated-type constant pattern; retrieval remains computed evidence. |
| `lean.declaration.inspect` | Resolve one exact declaration with type, kind, docs, source metadata, and pinned environment digest. |
| `lean.check` | Check a Lean proof in an operator-pinned environment and return its replay evidence. |
| `lean.proof_state.apply_tactic` | Apply one tactic through the pinned Lean REPL and materialize the resulting goals and replay source. |
| `lean.retrieve.premises` | Ask pinned Mathlib `exact?` for bounded candidate tactics and declaration references for one proof state. |
| `linear.rational_solution.verify` | Independently replay every equation for one exact stored vector; rejection does not prove inconsistency. |
| `matrix.normal_form.hermite.verify` | Independently check `H = U A`, `det(U) = ±1`, and every FLINT row-HNF condition for one exact stored candidate. |

The two exploratory Lean capabilities use the maintained
`leanprover-community/repl` JSON protocol pinned in the Lake manifest. Their
computed transitions and suggestions are not proof certificates. A completed
source still requires `lean.check`, whose independent checker binds the exact
statement, proof, environment, allowed axioms, and runtime revisions.

Operator-installed adapters appear in the same catalog. Agents should call
`capability.describe` before invoking an unfamiliar capability instead of
guessing payload fields. The
[Lean declaration discovery contract](lean-declaration-discovery.md) defines
its matching, coverage, environment identity, and assurance semantics.

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
