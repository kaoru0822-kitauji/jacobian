# Contributing to Jacobian

Jacobian is pre-stable. It exposes composable mathematical capabilities that
AI agents use to investigate conjectures and other mathematically specified
problems. Contributions should preserve mathematically atomic, agent-visible
outcomes, agent-owned composition, and the boundary between heuristic search
or evaluation and independently verified evidence.

## Before changing code

Read the [documentation home](docs/index.md), the
[product goals](docs/explanation/goals.md), the
[v0.2 frozen specification](docs/reference/specifications/v0.2.md), and the
[v0.2 conformance specification](docs/reference/conformance-v0.2.md).
Later pre-stable package versions extend that snapshot; use the installed
catalog and current reference documents for present capability membership.

## Development environment

Jacobian uses Python 3.12, `uv`, and a small `Makefile` that keeps local
commands aligned:

```sh
make setup
make test-fast
```

`make test-fast` is the short sequential non-integration feedback loop; it
excludes tests explicitly marked `slow`. `make test-unit-fast` is the smaller
unit-only lane used by the pre-push `make check`; contract, checker, and
reference tests remain available through their focused targets and CI. `make
test-core` runs the same core directories with default xdist parallelism and
includes `slow` cases; CI's core lane uses that target. Run `make check` before
pushing; it performs fast Ruff, strict typing, and `test-unit-fast`. Push after
that check and let CI own
path-planned validation: static analysis, package builds, planned Python lanes,
and Lean/npm/security/duplicate-code when the impact manifest selects them.
Coverage and Python 3.13 compatibility run only on exhaustive plans (merge
queue and `main`). `make check-static` reproduces CI's static checks plus a
local package build when a focused change needs them. `make validate-full` is
the broadest local Python, Lean, static, and package validation target. It does
not reproduce CI's Python 3.13 compatibility, combined coverage, security,
duplicate-code, or npm lanes (`make security-audit`, `make duplicate-code`, and
`make npm-test` cover those locally). Run `make help` for focused commands. The
measured costs and reasoning behind these lanes are recorded in the
[test-suite cost audit](docs/contributing/test-suite-cost-audit.md).
Tests can be narrowed without learning another wrapper:

```sh
make test TESTS=tests/integration/infrastructure/test_mcp_adapter.py
make test TESTS=tests/integration/infrastructure/test_mcp_adapter.py PYTEST_ARGS="-k schema -n 0"
make test-contracts
make test-checkers
make test-subprocess
make test-mcp PYTEST_ARGS="-k authentication"
make test-storage PYTEST_ARGS="-k workspace"
make test-lean TESTS=tests/integration/lean/test_lean.py PYTEST_ARGS="-k induction"
```

All Makefile pytest targets print their ten slowest tests by default. Set
`PYTEST_DIAGNOSTIC_ARGS=--durations=0` to suppress that report, or use a larger
value such as `PYTEST_DIAGNOSTIC_ARGS=--durations=25` while investigating a
regression.

Run `make hooks` once to install commit-time formatting, syntax, secret,
large-file, dead-code, and actionlint hooks plus the fast `make check`
pre-push gate. `make check` runs Ruff, mypy, and the unit-only fast lane;
contract, checker, and reference suites remain in CI. Use
`make pre-push-full` when a local push also needs the sequential core tests.
Hooks remain bypassable for exceptional cases with Git's standard
`--no-verify` option.
`make fix` applies Ruff's safe lint fixes followed by formatting. `make
precommit` applies those fixes and then runs the routine handoff checks.

On macOS, read the
[Z3 installation note](README.md#macos-and-z3) before troubleshooting a
source-build failure from `uv sync --dev`.

Use focused tests while implementing. Run `make check` before pushing and wait
for green CI checks before merge. Run broad local validation only when changing
CI itself, debugging an environment-specific failure, or when CI is
unavailable; use `make validate-full` for that exceptional path and rely on CI
for its additional lanes. Report only checks that actually ran. The manually
dispatched Python Debug and Lean Debug workflows reproduce one pytest file or
node in a prepared remote environment when the relevant local runtime is
impractical.

CI classifies pull requests through the tested source-to-suite impact
manifest in `.github/ci-impact.json`. Documentation-only changes skip
Python, npm, Lean, static, package, security, and duplicate-code lanes, but
run the dedicated `make docs-linkcheck` lane.
Documentation plus npm or npm-only changes run npm packaging without the
Python and Lean lanes. Unknown paths fail closed to all functional lanes.
Required status contexts still complete after checking the plan when their
expensive validation is intentionally omitted.
Maintainers can add the `ci:full` label to force every lane or `ci:lean` to
add real-Lean validation to an otherwise isolated plan. Label changes re-trigger
CI so the override applies without an extra push. These overrides only add work;
labels cannot reduce the fail-closed path classification.
Pull requests run the canonical Python version. Merge-queue groups and pushes
to `main` additionally run supported-version compatibility and combined
coverage as exhaustive gates. Successful `main` runs publish fresh integration
shard timings. Timing history is not committed, and missing or invalid history
falls back to equal-weight sharding.

Use `make test-plan BASE=<revision>` to preview the same changed-path routing
before validation:

| Change | Local handoff | CI adds |
| --- | --- | --- |
| Docs only | `make docs-linkcheck` | Documentation |
| Focused Python | affected target, then `make check` | Planned Python/static/package lanes |
| Lean runtime | focused `make test-lean`, then `make check` | Lean plus affected lanes |
| CI, dependencies, or unknown paths | `make check-static` plus affected tests | Fail-closed functional lanes |

Freeze the behavioral tree before the final broad validation. Record its tree
digest and HEAD SHA in the receipt produced by
`make validation-receipt COMMAND='make check'`, together with the
`make test-plan BASE=<revision>` selection and
checks that actually ran. If the tree changes, discard only evidence invalidated
by that change and rerun it; do not describe results from an earlier tree as
final-tree validation.

Parallel agents sharing one checkout must divide path ownership before editing.
They must not switch branches, stage, commit, clean, or rewrite shared files
while another agent is working. Integrate their edits first, freeze one tree,
then run the planned checks through `make validation-receipt` and produce one
receipt for that exact
tree. Use isolated worktrees only when the workflow explicitly assigns them.

Keep the local edit loop on directory-owned Make targets rather than inventing
marker filters:

```sh
make test-fast
make test-core
make test TESTS=tests/integration/infrastructure/test_mcp_adapter.py
```

Ownership is by test directory, not by `integration` / `end_to_end` markers.
Tests marked `lean_runtime` run serially through `make test-lean`; keep them out
of the normal xdist pool because Mathlib processes can retain several
gigabytes. CI installs the pinned Lean toolchain and Mathlib cache in a
dedicated pair of serial lanes on separate runners.
Use `uv run --locked pytest --lf` after a failure, `uv run --locked pytest -n 0`
while debugging, and `make check` before pushing. Use
`make test-lean TESTS=path/to/test.py` for
a deliberately focused local Lean reproduction, or dispatch the remote Lean
debug workflow from GitHub Actions when local Lean is impractical. Use
`make test-lean PYTEST_ARGS=--lf` to rerun a failed Lean-runtime test.
Do not use unfiltered `uv run pytest` as the normal complete-suite command
because it mixes Lean into the general xdist pool; pytest rejects that unsafe
combination with the corresponding `make` targets in its error message.
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

Keep rolling product goals separate from supported release behavior.
For hosted MCP changes, update and validate
[`docs/how-to/deploy-remote-mcp.md`](docs/how-to/deploy-remote-mcp.md) together
with any affected files under `deploy/`. Do not promote ignored `tmp/`
configuration or deployment notes into source-of-truth instructions.
For documentation-only changes, run:

```sh
git diff --check
git diff -- AGENTS.md README.md CONTRIBUTING.md docs/
make docs-linkcheck
```

Verify every relative Markdown link before submitting the change
(`make docs-linkcheck` checks project Markdown offline).

## Releases

The manifest-driven Release Please configuration keeps the Python and npm
package versions synchronized. CI tests and packs the npm launcher
independently, then publishes both distributions after a release is created.
The `jacobian` package on npm must authorize `.github/workflows/release.yml` as
its trusted GitHub Actions publisher, using the `npm` environment; releases use
OIDC rather than a long-lived npm token.

## Pull requests

Keep each change focused on one outcome. Explain the problem, the resulting
behavior or contract, any compatibility impact, and the validation performed.
Link a relevant issue when one exists. Include screenshots only when rendered
layout or diagrams materially change.

## Test ownership and selection

Test directories define semantic ownership: `tests/unit`, `tests/contract`,
`tests/checkers`, and `tests/reference` form the core suite, while
`tests/integration` and `tests/end_to_end` form the integration suite. Use
`make test-core` and `make test-integration` as the canonical entry points.
Markers describe runtime traits such as `lean_runtime`, `slow`, `subprocess`, or
`external_backend`; they do not duplicate directory ownership. Reproduce the
scheduled validation lanes locally with `make test-stress` and
`make test-ordering PYTEST_ARGS=--randomly-seed=17` (locked `pytest-repeat` and
`pytest-randomly` are part of the dev environment).
Use `make test-subprocess` to run the clean-process replay tests selected by the
`subprocess` marker. The marker is a selection label; it does not serialize
unrelated tests under xdist.

CI change impact is declared in `.github/ci-impact.json`. Its matching rules are
additive, so a path may require several suites. Integration timing history is a
scheduling hint produced by successful `main` runs; it is not committed state,
and missing or invalid history falls back to equal-weight sharding.
