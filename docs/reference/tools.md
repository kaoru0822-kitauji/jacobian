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

## Installed capability discovery

The installed catalog is the canonical capability inventory. Its membership
depends on the available provider runtimes, operator-authorized checkers,
enabled bundled references, configured exclusions, and operator-installed
adapters. A static list in this document would therefore describe only one
installation snapshot.

Read `capability://catalog`, or call `capability.describe` without a capability
ID, for the exact installed IDs and compact descriptors. Call
`capability.describe` with one ID before invocation to inspect its complete
input and output schemas, supported modes, provider identity, availability,
and checker requirements. Do not infer installation or payload fields from
examples in documentation.

Domain reference documents define constraints that remain useful independent
of catalog membership:

- [SAT artifact contracts](sat-artifacts.md);
- [SMT Alethe artifact contracts](smt-artifacts.md);
- [exact rational linear-system evidence](linear-rational-solutions.md);
- [exact rational matrix determinants](matrix-rational-determinant.md);
- [integer matrix Hermite normal form](matrix-hermite-normal-form.md);
- [fixed-registry graph invariant batches](graph-invariant-batch.md);
- [typed polynomial expression normalization](polynomial-expression-normalization.md);
- [Lean declaration discovery contract](lean-declaration-discovery.md).

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

Opaque multi-stage commands are not part of the public surface. Agents should
compose generation, evaluation, ranking, falsification,
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
