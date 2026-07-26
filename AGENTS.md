# Repository Guidelines

## Product Model

Jacobian is an MCP server, CLI, and Python library that exposes a toolbox of
composable mathematical capabilities to AI agents. Its purpose is to help
agents and human researchers make trustworthy progress on conjectures and
other problems that benefit from executable search and checkable evidence.

The product follows five design principles:

- broad portfolio of mathematical capabilities;
- mathematically atomic, agent-visible outcomes;
- agent-owned composition and research strategy;
- optional workflows with inspectable intermediate artifacts;
- independent verification of exact claims and evidence.

Each capability provides one clear mathematical operation, such as retrieving
premises, constructing an object, computing an invariant, transforming a
claim, searching for a witness, or checking a certificate. It returns typed
results and, where materialized, durable artifacts with explicit execution
status, provenance, scope, completeness, exactness, and assurance. Descriptors
and results must distinguish exact from approximate, bounded from exhaustive,
and deterministic from heuristic behavior. They must also state completion,
certificate availability, and any checker required for promotion. Search,
generation, and computation produce evidence; they do not verify their own
conclusions.

Agents compose capabilities into higher-level strategies, much as
mathematicians combine definitions, examples, computations, constructions,
lemmas, transformations, and proof techniques. Agents may discover, combine,
repeat, compare, or abandon capabilities. Jacobian supplies mathematical
operations and trust boundaries; it does not prescribe a proof workflow.
Better models should be able to use the same portfolio more effectively
without kernel changes.

Prefer capabilities with one observable mathematical outcome. Do not hide
useful intermediate objects, computations, failures, relationships, or proof
obligations inside opaque workflow tools. Agent-visible mathematical atomicity
matters; backend-call atomicity does not. A capability may coordinate several
backend operations when they jointly produce one coherent outcome.

Design capabilities with the existing portfolio in mind. Prefer consuming an
existing typed artifact when it already exposes the needed mathematical
outcome. Temporary or justified overlap is acceptable for experimentation,
performance, batching, backend constraints, or a genuinely different
agent-visible outcome. Make the overlap explicit and preserve useful
intermediate artifacts.

Higher-level workflows belong in agent strategies and reusable skills. A
workflow exposed as a capability must preserve its intermediate artifacts,
relationships, obligations, scope, assurance, and independent verification
boundaries.

Installed capabilities are currently exposed through
`capability://catalog`; agents inspect exact contracts with
`capability.describe` and execute them with `capability.invoke`. As the
portfolio grows, discovery should return compact summaries first and add
catalog search and ranking instead of injecting every installed schema into
the agent's initial context. Prefer a namespaced capability ID over a new
top-level MCP tool.

Capability availability, recommendation, compatibility, and verification
authority are separate:

- Available capabilities may be discovered and invoked.
- Recommendations are evidence-based routing hints, not access restrictions.
- Experimental capabilities may use version-breaking contracts.
- Compatibility applies only to explicitly supported contract versions.
- `VERIFIED` requires an operator-authorized checker independent of the
  proposing, searching, or evaluating implementation.

Use held-out evaluations and real transcripts to improve discovery, examples,
ranking, defaults, consolidation, and retirement. Before stabilizing or
recommending a capability, query the catalog by domain, artifact types, and
mathematical outcome, then inspect the small set of closest matches. If overlap
remains ambiguous or the decision is consequential, compare the current
portfolio with and without the candidate. Do not require exhaustive pairwise or
leave-one-out evaluation for routine additions. Let agents choose tools when
measuring autonomous composition; prescribed-tool cases test contract usability
and conformance, not portfolio value.

Capability names are descriptive, not a closed taxonomy, universal operation
enum, or shared mathematical ontology. Do not create a generic mathematical
object schema, one capability for every mathematical verb, or mechanical
wrappers for every backend function. Prefer specific IDs and domain-owned
contracts, such as `graph.enumerate.nonisomorphic` or
`polynomial.compute.groebner_basis`.

Before implementing mathematics, check whether a maintained proof assistant,
CAS, solver, optimization system, mathematical database, or domain library
already provides it. Prefer thin adapters over reimplementation. Pin backend
versions wherever reproducibility, certificates, or verification depend on
their behavior. Examples include Lean/mathlib, SageMath, GAP, OSCAR, SymPy,
SAT/SMT solvers, and specialized domain systems.

The kernel owns artifact identity, execution status, assurance, checker
authorization, budgets, and provenance. It governs trust and execution policy,
not mathematical strategy. Capability adapters own external integrations.
Domain plugins own mathematical schemas, transformations, invariants, witness
meanings, and required checker roles. Independent checker packages implement
replay; operators authorize them. Agent workflows and skills own multi-step
exploration. Worked cases belong in reference scenarios and benchmarks.

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

Jacobian is pre-stable. Release specifications describe supported snapshots;
they do not prescribe the order in which mathematical capabilities are
researched or exposed.

- `src/jacobian/` contains the kernel, contracts, adapters, and domain code.
- `src/jacobian_checkers/` contains independent replay code.
- `tests/` contains behavioral and conformance tests.
- `README.md` provides the project overview.
- `docs/index.md` is the documentation home.
- `docs/tutorials/` contains guided learning paths.
- `docs/how-to/` contains task-oriented operating guides.
- `docs/reference/` contains tools, conformance requirements, specifications,
  benchmarks, and testing protocols.
- `docs/explanation/` contains architecture, threats, product goals, runtime
  design, and numbered ADRs.
- `docs/contributing/` contains maintainer-facing planning material.

Keep `deep_review.md` local. It is intentionally ignored and is not design
source material.

## Build, Test, and Development Commands

The project uses Python 3.12 and `uv`. Install the locked development
environment, then run:

```sh
uv sync --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv build
```

For documentation changes, also run:

```sh
git diff --check
git diff -- AGENTS.md README.md docs/
```

`git diff --check` catches whitespace errors. The focused diff supports review
of public documentation.

## Writing Style & Naming Conventions

Write concise Markdown with ATX headings (`#`, `##`) and descriptive link text.
Lead with the concrete decision, behavior, or invariant. Cut generic
introductions, repeated summaries, and direction claims unsupported by current
code or a named plan.

Wrap prose at a readable width consistent with nearby files. Preserve the
distinction between search or evaluation results and independently verified
evidence. Name specifications by release (`v0.2.md`) and ADRs with a
zero-padded sequence plus kebab-case description. Update `README.md` when
adding a public-facing document.

## Testing Guidelines

Check changes against the applicable release specification,
`docs/reference/conformance-v0.2.md`, and
`docs/reference/testing-strategy.md`. Verify relative links. Do not present
rolling product goals as a stable contract. Report only checks that
actually ran.

## Commit & Pull Request Guidelines

Use short, imperative commit subjects. Scope them when useful, for example
`docs: clarify capability trust boundaries`. Keep each commit focused on one
coherent outcome.

Pull requests must explain the problem, the resulting change, and any
compatibility or normative impact. Link the relevant issue when one exists.
Include screenshots only when layout or diagrams materially change. List the
exact validation performed.

## Security & Verification

Evidence becomes verified only after an authorized checker accepts data bound
to the exact claim, semantics, candidate, scope, certificate format, and
checker version. Do not weaken this invariant. Discuss trust-boundary changes
alongside `docs/explanation/threat-model.md`.
