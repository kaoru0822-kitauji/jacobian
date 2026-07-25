# Contributing to Jacobian

Jacobian is pre-stable. It exposes composable mathematical capabilities that
AI agents use to investigate conjectures and other mathematically specified
problems. Contributions should preserve mathematically atomic, agent-visible
outcomes, agent-owned composition, and the boundary between heuristic search
or evaluation and independently verified evidence.

## Before changing code

Read the [documentation home](docs/index.md), the
[product goals](docs/explanation/goals.md), the
[v0.2 specification](docs/reference/specifications/v0.2.md), and the
[v0.2 conformance specification](docs/reference/conformance-v0.2.md).
Changes to checker authorization, plugin isolation, durable state, or evidence
promotion also require reviewing the
[threat model](docs/explanation/threat-model.md).

## Development environment

Jacobian uses Python 3.12 and `uv`:

```sh
uv sync --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv build
```

On macOS, read the
[Z3 installation note](README.md#macos-and-z3) before troubleshooting a
source-build failure from `uv sync --dev`.

Use focused tests while implementing. Run the complete applicable validation
before handing off the final tree, and report only checks that actually ran.

## Verification rules

- Do not turn a timeout, cancellation, error, incomplete enumeration, or
  missing witness into a mathematical conclusion.
- Do not promote an evaluator score, solver status, model answer, or search
  result directly to `VERIFIED`.
- Keep execution status, input validity, mathematical conclusion, assurance,
  and evidence type separate.
- Bind verified evidence to the exact claim, semantics, candidate, scope,
  certificate format, and checker identity.
- Keep checker authorization and trust policy outside untrusted plugins and
  search workers.

For trust-sensitive changes, write the failing invariant or attack test first
and verify replay through an independent checker process.

## Documentation

Place documentation according to the reader's task:

- `docs/tutorials/` teaches through a complete guided experience;
- `docs/how-to/` explains how to complete one specific task;
- `docs/reference/` defines exact contracts and lookup information;
- `docs/explanation/` records architecture, rationale, and tradeoffs.

Update `docs/index.md` and the root `README.md` when adding a public entry
point. Keep rolling product goals separate from supported release behavior.
For documentation-only changes, run:

```sh
git diff --check
git diff -- README.md CONTRIBUTING.md docs/
```

Verify every relative Markdown link before submitting the change.

## Pull requests

Keep each change focused on one outcome. Explain the problem, the resulting
behavior or contract, any compatibility impact, and the validation performed.
Link a relevant issue when one exists. Include screenshots only when rendered
layout or diagrams materially change.
