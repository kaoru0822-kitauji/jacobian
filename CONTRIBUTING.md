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

## Development environment

Jacobian uses Python 3.12, `uv`, and a small `Makefile` that keeps local
commands aligned:

```sh
make setup
make test-fast
```

`make test-fast` is the short non-integration feedback loop. Run `make check`
before pushing; it performs fast Ruff and non-integration test checks. Push
after that check and let CI own dependency and dead-code analysis, strict
typing, package builds, the full Python matrix, integration, end-to-end,
coverage, and real-Lean validation. `make check-static` reproduces the
CI-owned static and package checks when a focused change needs them.
`make validate-full` is only for reproducing exhaustive CI validation locally
when CI is unavailable or an environment-specific failure requires it. Run
`make help` for focused commands. The measured costs and reasoning behind
these lanes are recorded in the
[test-suite cost audit](docs/contributing/test-suite-cost-audit.md).
Tests can be narrowed without learning another wrapper:

```sh
make test TESTS=tests/integration/test_mcp_adapter.py
make test TESTS=tests/integration/test_mcp_adapter.py PYTEST_ARGS="-k schema -n 0"
make test-contracts
make test-checkers
make test-mcp PYTEST_ARGS="-k authentication"
make test-storage PYTEST_ARGS="-k workspace"
make test-lean TESTS=tests/integration/test_lean.py PYTEST_ARGS="-k induction"
make refresh-test-durations
make refresh-lean-test-durations
```

Run `make hooks` once to install the repository's formatting, syntax, secret,
and large-file checks. `make fix` applies Ruff's safe lint fixes followed by
formatting.

On macOS, read the
[Z3 installation note](README.md#macos-and-z3) before troubleshooting a
source-build failure from `uv sync --dev`.

Use focused tests while implementing. Run `make check` before pushing and wait
for green CI checks before merge. Run complete local validation only
when changing CI itself, debugging an environment-specific failure, or when CI
is unavailable; use `make validate-full` for that exceptional path. Report only
checks that actually ran. The manually dispatched Python Debug and Lean Debug
workflows reproduce one pytest file or node in a prepared remote environment
when the relevant local runtime is impractical.

CI classifies pull requests conservatively. Documentation-only changes skip
Python, npm, Lean, static, package, security, and duplicate-code lanes.
Documentation plus npm or npm-only changes run npm packaging without the
Python and Lean lanes. Source, dependency, workflow, mixed, empty, and unknown
change sets run complete validation, as does every push to `main`.
Maintainers can add the `ci:full` label to force every lane or `ci:lean` to
add real-Lean validation to an otherwise isolated plan. These overrides only
add work; labels cannot reduce the fail-closed path classification.

For a quick local feedback loop, skip the integration and end-to-end layers:

```sh
uv run pytest -m "not integration and not end_to_end"
```

Pytest assigns these layer markers from the test directories, so new
integration tests join the right loop without repeated file-level boilerplate.
Tests marked `lean_runtime` run serially through `make test-lean`; keep them out
of the normal xdist pool because Mathlib processes can retain several
gigabytes. CI installs the pinned Lean toolchain and Mathlib cache in a
dedicated pair of serial lanes on separate runners.
Use `uv run pytest --lf` after a failure, `uv run pytest -n 0` while debugging,
and `make check` before pushing. Use `make test-lean TESTS=path/to/test.py` for
a deliberately focused local Lean reproduction, or dispatch the remote Lean
debug workflow from GitHub Actions when local Lean is impractical. Use
`make test-lean PYTEST_ARGS=--lf` to rerun a failed Lean-runtime test.
Do not use unfiltered `uv run pytest` as the normal complete-suite command
because it mixes Lean into the general xdist pool.
Refresh `.test_durations` after major suite changes; the target replaces the
committed timings only after a successful non-Lean run on Linux with Python
3.12. Also refresh when the slower CI shard exceeds the faster shard by more
than 10% in two representative runs. Do not refresh for routine test edits.
Refresh `.lean_test_durations` after adding or materially changing
`lean_runtime` tests; its target runs all Lean tests serially before replacing
the committed file.

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
git diff -- AGENTS.md README.md CONTRIBUTING.md docs/
```

Verify every relative Markdown link before submitting the change.

## Releases

The manifest-driven Release Please configuration keeps the Python and npm
package versions synchronized. CI tests and packs the npm launcher
independently, then publishes both distributions after a release is created.
The `jacobian` package on npm must authorize `.github/workflows/ci.yml` as its
trusted GitHub Actions publisher, using the `npm` environment; releases use
OIDC rather than a long-lived npm token.

## Pull requests

Keep each change focused on one outcome. Explain the problem, the resulting
behavior or contract, any compatibility impact, and the validation performed.
Link a relevant issue when one exists. Include screenshots only when rendered
layout or diagrams materially change.
