# Repository Guidelines

Follow [CONTRIBUTING.md](CONTRIBUTING.md) for setup, validation, documentation,
commits, and pull requests. This file lists only Jacobian-specific constraints.
Load the [product model](docs/explanation/product-blueprint.md),
[goals](docs/explanation/goals.md), or
[tool reference](docs/reference/tools.md) when needed. For built-in mathematical
operations, also use the
[domain operation library reference](docs/reference/domain-operation-library.md).

## Product Constraints

Jacobian gives agents composable mathematical capabilities. Its principles are:

- a broad mathematical portfolio;
- atomic, agent-visible outcomes;
- agent-owned composition and research strategy;
- inspectable intermediate artifacts; and
- independent verification of exact claims and evidence.

Each capability exposes one coherent, inspectable mathematical outcome. It may
coordinate backend calls, but useful intermediate artifacts, failures,
relationships, scope, completeness, assurance, and proof obligations remain
visible.

Jacobian exposes mathematical affordances, not research policy. Capabilities
must remain atomic, searchable, and freely composable. Do not prescribe
preferred decompositions, proof strategies, cross-capability workflows,
verification order, or stopping criteria through discovery, ranking, prompts,
or adapters. Capabilities may implement specific mathematical methods, while
agents remain free to choose and compose them. Prompts and resources may
explain protocol and evidence semantics, but remain optional.

Design against the existing portfolio. Reuse typed artifacts that expose the
needed outcome; declare overlap and keep useful intermediates. Before
stabilizing or recommending a capability, inspect nearby catalog entries by
domain, artifact type, and outcome. If overlap remains ambiguous or
consequential, use the
[evaluation plan](docs/reference/capability-workflow-evaluations.md). Routine
additions need no exhaustive pairwise or leave-one-out evaluation.

Use `capability.describe(query=...)` for intent-led search,
`capability.describe(capability_id=...)` for exact contracts and invocation
examples, and `capability.invoke` to execute. Use `capability://catalog` for the
complete machine-readable inventory. Prefer domain-owned capability IDs to
generic schemas, verb taxonomies, mechanical backend wrappers, or new top-level
MCP tools.

Prefer thin adapters to maintained mathematical systems. Pin versions when
reproducibility, certificates, or verification depend on them.

Built-in mathematical producers belong in explicit domain bundles. Do not add
global operation registries, recursive package discovery, import-time
registration, or mechanical wrappers for backend functions. Producers remain
capped at `COMPUTED`; domain-owned checker declarations do not authorize
themselves.

Keep availability, recommendations, compatibility, and verification authority
separate. Experimental contracts may break between versions; compatibility
applies only to supported versions. Only an operator-authorized checker
independent of proposal, search, and evaluation may return `VERIFIED`.

Follow the
[ownership model](docs/explanation/product-blueprint.md#ownership-model).
Keep strategy out of the kernel, semantics out of generic contracts, and
checker authorization out of plugins and search code.

## Fail-Closed Verification Rules

- Treat `TIMEOUT`, `CANCELLED`, `ERROR`, incomplete enumeration, and failure to
  find a witness as non-conclusions.
- Never promote an evaluator score, solver status, model answer, or search
  result directly to `VERIFIED`.
- Keep execution status, input validity, mathematical conclusion, assurance,
  and evidence type separate.
- Bind `VERIFIED` evidence to the exact claim, semantics, candidate, scope,
  certificate format, and checker identity.
- Plugins and search code cannot authorize checkers or change trust policy.
- Independent checkers cannot depend on the search implementation they certify.

## Repository Gotchas

- Jacobian is pre-stable. Release specifications capture supported snapshots;
  they do not order capability research.
- Validate the complete Pydantic request model before computation or artifact
  writes. JSON Schema supports discovery; it does not replace cross-field
  validation.
- `COMPLETED` bounded execution may still have `UNKNOWN` completeness and open
  obligations. Execution completion does not establish optimality or a
  mathematical conclusion.
- Include every first-class artifact reference, including verification records,
  in the result's `artifact_uris`.
- An unavailable optional provider must remove only the affected capabilities;
  unrelated kernel startup and catalog entries remain available.
- Keep `deep_review.md` local; it is ignored and is not design source material.
- Keep worked cases in reference scenarios and benchmarks.
