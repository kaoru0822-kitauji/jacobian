# Repository Guidelines

Follow [CONTRIBUTING.md](CONTRIBUTING.md) for setup, validation, documentation,
commits, and pull requests. This file lists only Jacobian-specific constraints.
Load the [product model](docs/explanation/product-blueprint.md),
[goals](docs/explanation/goals.md), or
[tool reference](docs/reference/tools.md) when needed.

## Product Constraints

Jacobian gives agents composable mathematical capabilities. Its principles are:

- a broad mathematical portfolio;
- atomic, agent-visible outcomes;
- agent-owned composition and research strategy;
- inspectable intermediate artifacts; and
- independent verification of exact claims and evidence.

Each capability exposes one coherent mathematical outcome. It may coordinate
backend calls, but useful intermediate objects, failures, relationships, and
proof obligations remain visible. Results and artifacts report execution
status, provenance, scope, completeness, exactness, assurance, completion,
available certificates, and required checkers.

Agents own multi-step strategy. Put workflows in agent strategies and skills.
Workflow capabilities must expose intermediate artifacts and verification
boundaries.

Design against the existing portfolio. Reuse typed artifacts that expose the
needed outcome; declare overlap and keep useful intermediates. Before
stabilizing or recommending a capability, inspect nearby catalog entries by
domain, artifact type, and outcome. If overlap remains ambiguous or
consequential, use the
[evaluation plan](docs/reference/capability-workflow-evaluations.md). Routine
additions need no exhaustive pairwise or leave-one-out evaluation.

Use `capability://catalog` to discover capabilities, `capability.describe` to
inspect contracts, and `capability.invoke` to execute them. Prefer domain-owned
IDs to generic schemas, verb taxonomies, mechanical backend wrappers, or new
top-level MCP tools.

Prefer thin adapters to maintained mathematical systems. Pin versions when
reproducibility, certificates, or verification depend on them.

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
- For trust-sensitive changes, write the attack or invariant test first,
  replay it in a clean process, and update
  `docs/explanation/threat-model.md`.

## Repository Gotchas

- Jacobian is pre-stable. Release specifications capture supported snapshots;
  they do not order capability research.
- Validate the complete Pydantic request model before computation or artifact
  writes. JSON Schema supports discovery; it does not replace cross-field
  validation.
- Keep `deep_review.md` local; it is ignored and is not design source material.
- Keep worked cases in reference scenarios and benchmarks.
