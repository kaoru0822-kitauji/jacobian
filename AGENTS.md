# Repository Guidelines

## Project Purpose and Decision Rules

Jacobian is a verifier-centric research workbench for bounded, executable
mathematics. It gives models and researchers a laboratory in which they can
propose candidates, search finite spaces, receive structured counter-witnesses,
shrink discoveries, and replay independently checked certificates.

Jacobian is not a `solve_conjecture` endpoint, a universal mathematics
ontology, or a replacement for existing SAT, SMT, optimization, and proof
engines. Search, generation, evaluation, and interpretation may be heuristic
or wrong. Only an operator-authorized checker may promote evidence to a
verified result.

The generic kernel understands artifacts, claims, candidates, predicates,
witnesses, certificates, reductions, budgets, and provenance. Mathematical
semantics belong in versioned domain plugins. Do not add graph-, matrix-,
routing-, solver-, or proof-system-specific types to the generic core merely
to satisfy a reference scenario.

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

Jacobian is currently a specification-first research project; there is no
implementation tree or stable public API yet. `README.md` provides the project
overview and document index. Design material lives in `docs/`:

- `docs/specifications/` contains versioned release specifications. v0.1 is the
  only normative implementation target; later versions are provisional.
- `docs/adr/` records architectural decisions using numbered filenames such as
  `0001-python-first-control-plane.md`.
- Top-level documents cover architecture, tools, conformance, threats,
  benchmarks, testing strategy, and the roadmap.

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
(`v0.1.md`) and ADRs with a zero-padded sequence plus kebab-case description.
Update `README.md` when adding a public-facing document.

## Testing Guidelines

Treat cross-document consistency as the current validation target. Check new
claims against `docs/specifications/v0.1.md`,
`docs/conformance-v0.1.md`, and `docs/testing-strategy.md`. Verify relative
links and ensure provisional roadmap material is not presented as a stable
contract. Report manual checks accurately; do not claim executable tests that
were not run.

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
`docs/threat-model.md`.
