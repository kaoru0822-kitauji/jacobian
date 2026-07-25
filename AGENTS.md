# Repository Guidelines

## Product Model

Jacobian is a verifier-centric workbench for investigating mathematical
problems, including research-level conjectures, through bounded, executable
steps. Mathematician agents and human researchers compose small capabilities to
transform claims, construct and explore mathematical objects, search for
counterexamples, build candidate proofs, and submit evidence to independent
checkers.

A mathematical primitive is a versioned capability that performs one
observable operation. It consumes typed artifacts and returns typed artifacts,
their explicit relationships, any new proof obligations, and the execution,
assurance, and provenance needed to inspect or replay the step. A primitive may
search, generate, transform, retrieve, or evaluate; it cannot promote its own
output to verified evidence.

Primitive operations include deriving related claims; constructing,
enumerating, mutating, or searching mathematical objects; computing properties
and invariants; partitioning cases; decomposing goals; retrieving and
instantiating premises; and replaying or cross-checking certificates. This list
does not define a universal mathematical ontology. Domain plugins define the
meaning of each operation for their objects and claims.

Proof strategies and research agents compose primitives into workflows.
External SAT, SMT, CAS, optimization, retrieval, and proof systems connect
through capability adapters. Prefer a capability ID behind
`capability.describe` and `capability.invoke` over a new top-level MCP tool.

The kernel owns artifact identity, execution status, assurance, checker
authorization, budgets, and provenance. Capability adapters own external
integrations. Domain plugins own mathematical schemas, transformations,
invariants, witness meanings, and checkers. Agent workflows and skills own
multi-step exploration policies. Worked cases belong in reference scenarios
and benchmarks.

## Fail-Closed Verification Rules

- Never convert `TIMEOUT`, `CANCELLED`, `ERROR`, incomplete enumeration, or
  failure to find a witness into a mathematical conclusion.
- Never promote an evaluator score, solver status, model answer, or search
  result directly to `VERIFIED`.
- Keep execution status, input validity, mathematical conclusion, assurance,
  and evidence type separate.
- Bind verified evidence to the exact claim, domain semantics, candidate,
  scope, certificate format, and checker identity.
- Untrusted plugins and search code must not authorize checkers or alter trust
  policy.
- Independent checkers must not depend on the search implementation whose
  output they certify.
- For trust-sensitive changes, write the attack or invariant test first and
  verify replay in a clean process.

## Project Structure & Module Organization

Jacobian v0.2 alpha is the current cumulative implementation under
`src/jacobian/`, with independent replay code under
`src/jacobian_checkers/` and behavioral tests under `tests/`. It is the only
current release contract; earlier development milestones survive only as
ordinary regression coverage. The public API and artifact formats remain
pre-stable.
`README.md` provides the project overview, while `docs/index.md` is the
documentation home. Design material lives in `docs/`:

- `docs/tutorials/` contains guided learning paths.
- `docs/how-to/` contains task-oriented operating guides.
- `docs/reference/` contains tools, conformance requirements, specifications,
  milestone contracts, benchmarks, and testing protocols.
- `docs/explanation/` contains architecture, threats, the roadmap, runtime
  design, and numbered ADRs.
- `docs/contributing/` contains maintainer-facing planning material.

Keep `deep_review.md` local; it is intentionally ignored as design source
material.

## Build, Test, and Development Commands

The project uses Python 3.12 and `uv`. Install the locked development
environment and run the required checks with:

```sh
uv sync --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv build
```

For documentation-only changes, also use:

```sh
git diff --check
git diff -- README.md docs/
```

The first command catches whitespace errors. The second supports a focused
review of public documentation.

## Writing Style & Naming Conventions

Write concise Markdown with ATX headings (`#`, `##`) and descriptive link text.
Wrap prose at a readable width consistent with nearby files. Preserve the
project's precise distinction between search or evaluation results and
independently verified evidence. Name specifications by release
(`v0.2.md`) and ADRs with a zero-padded sequence plus kebab-case description.
Update `README.md` when adding a public-facing document.

## Testing Guidelines

Check changes against the applicable release specification,
`docs/reference/conformance-v0.2.md`, and
`docs/reference/testing-strategy.md`. Verify relative links and ensure
provisional roadmap material is not presented as a stable contract. Report
only checks that actually ran.

## Commit & Pull Request Guidelines

Recent commits use short, imperative subjects, commonly scoped as
`docs: <outcome>`, for example `docs: define verification kernel roadmap`.
Keep each commit focused on one coherent documentation outcome.

Pull requests should explain the problem, the resulting specification or
documentation change, and any compatibility or normative impact. Link the
relevant issue when one exists. Include rendered screenshots only when layout
or diagrams materially change, and list the exact validation performed.

## Security & Verification

Do not weaken the central invariant: evidence becomes verified only after an
authorized checker accepts data bound to the exact claim, semantics, candidate,
and checker version. Discuss changes affecting trust boundaries alongside
`docs/explanation/threat-model.md`.
