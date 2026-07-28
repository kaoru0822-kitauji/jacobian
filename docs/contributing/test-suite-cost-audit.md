# Test-suite cost audit

> **Historical baseline.** Counts and timings below describe the audit snapshot,
> not current mutable scheduling state. CI timing hints now come from successful
> `main` artifacts and may be absent without affecting test selection.

[Documentation home](../index.md)

This audit records the 2026-07-26 local measurements used to restore a short
edit-test loop without weakening Jacobian's verification boundary. Timings are
machine-local observations, not performance gates.

## 2026-07-28 bootstrap follow-up

A later profile found that kernel construction had regressed to 31.6 seconds
for a fresh core store. The main costs were repeated JSON Schema metaschema
validation and one durable SQLite transaction per descriptor. Bootstrap now
reuses exact-schema validation within the process and installs the capability
portfolio through one store-owned transaction. Ordinary artifact writes retain
their existing durability boundary.

On the same local host, fresh core construction fell from 31.6 to 13.0 seconds.
Attaching to a copied core snapshot took 0.79 seconds, and adding authorized
references to a copied core snapshot took 3.68 seconds. `make test-fast` fell
from 237.91 seconds wall time to 56.55 seconds while selecting 591 tests; three
exhaustive cases were explicitly marked `slow` and excluded from that lane.
These are single-host observations, not timing gates.

## Measured lanes

| Lane | Selected tests | Observed wall time | Purpose |
| --- | ---: | ---: | --- |
| Unfiltered `uv run pytest` | 546 | 372.48 s | Diagnostic baseline; mixes Lean into the general xdist pool |
| `make test-fast`, before this audit | 246 | 43.92 s | Non-integration edit loop |
| `make test-fast`, after fixture reuse | 246 | 6.55 s | Non-integration edit loop |
| Integration, excluding end-to-end and Lean | 275 | 218.88 s | Real stores, subprocesses, adapters, and capability composition |
| End-to-end | 5 | 33.84 s | Distinct complete mathematical workflows |
| `make test-lean` | 20 | 218.26 s | Serial pinned Lean and Mathlib coverage |

Static validation was not a material bottleneck: Ruff, formatting, mypy,
dependency checks, build, and documentation checks completed in about 16
seconds together.

## Findings

Most elapsed time is setup and boundary coverage, not repeated assertions.
Fresh `JacobianKernel` construction took roughly 2.4 to 3.3 seconds without
reference installation and 3.3 to 4.9 seconds with it. Integration tests
intentionally pay for real schema registration, artifact writes, SQLite and
filesystem behavior, checker subprocesses, plugin isolation, and provider
discovery. The slow Lean cases separately cover Mathlib discovery, real replay,
premise retrieval, declaration indexes, tampering, and evaluation traces.

Those costs protect different invariants. Do not reduce them by globally
disabling durable writes, sharing a mutable kernel between isolation tests,
replacing real filesystems with in-memory substitutes, or deleting
trust-boundary attacks.

One direct DRAT-trim checker module did repeat unrelated product setup. Each
parameter case constructed the full kernel even though it needed only SAT
artifact schemas and a request envelope. A module-scoped minimal real artifact
store now reuses immutable content-addressed artifacts while constructing an
isolated request value for each case. All attack cases remain. This reduced the
fast lane by about 85 percent, from 43.92 to 6.55 seconds.

Pull requests use stable core and integration/end-to-end lanes on the canonical
Python version. The integration lane is divided with pinned `pytest-split`
using committed test durations; xdist's `worksteal` scheduler balances each
shard across its runner's four CPUs. The merge queue adds the second supported
Python version and combined coverage, so exhaustive work remains a merge gate
without multiplying every review run.

## Development policy

Use the cheapest lane that preserves the boundary being changed:

```sh
make test-fast
make test TESTS=tests/integration/infrastructure/test_mcp_adapter.py
make test
make test-lean
make validate-full
```

`make test-fast` is the normal edit loop. Use focused integration tests while
changing stores, adapters, plugins, subprocesses, or checker execution.
`make check` combines fast Ruff checks, strict typing, and that loop.
Dependency and dead-code analysis and package builds remain available through
`make check-static` but are CI-owned rather than routine local handoff work.
`make test` runs the complete non-Lean suite, and `make test-lean` keeps the
memory-heavy backend serial. Neither is a routine pre-push requirement; CI
owns exhaustive validation.
`make validate-full` combines the broad local Python, Lean, static, and package
checks when CI is unavailable or an environment-specific failure requires it.
Python 3.13 compatibility, combined coverage, security, duplicate-code, and npm
validation remain separate CI lanes. Do not use unfiltered `uv run pytest` as
the default handoff command because it mixes Lean into the general parallel
pool.

The Lean suite runs serially on one prepared runner. This avoids concurrent
multi-gigabyte Mathlib processes, collects every `lean_runtime` test without a
file allowlist, and keeps the pinned toolchain setup attached to the tests that
consume it.

## Follow-up opportunities

- Profile kernel startup as a product concern before changing its durability
  or registration model.
- Reuse module fixtures only where inputs remain isolated and the shared state
  is immutable.
- Track lane wall times periodically; investigate changes before adding a
  blanket `slow` marker or weakening required coverage.
- Move backend combinations to a slower lane only when the pull-request lane
  still exercises every affected trust boundary.

## Follow-up audit

The expanded 537-test non-Lean suite has a median recorded case duration of
0.08 seconds, but its slowest five percent take at least 6.62 seconds. Those
cases are not interchangeable repetitions: they cover remote tenant isolation,
MCP and CLI process boundaries, interrupted-search recovery, clean-process
checker replay, SAT proof interoperability, and complete end-to-end workflows.
The two supported Python versions exercise runtime compatibility, while the
Lean lane exercises a separate pinned toolchain and checker boundary. Retain
those lanes.

An exploratory eight-worker run on an eight-logical-CPU, 32 GB Linux host
completed all 537 tests in 137.81 seconds, compared with about 170 seconds under
the four-worker default. This single-host result is not sufficient to raise the
default: the suite is subprocess-heavy, wall time changed substantially under
unrelated host load, and exhaustive local validation is deliberately not the
routine loop. Keep the stable four-worker cap and revisit it only with
controlled repeated measurements on local and CI runners.

The actionable redundancy was procedural. The routine `make check` lane now
contains only fast Ruff and non-integration tests; named contract, checker, MCP,
and storage targets expose common focused checks. CI skips heavy Python and
Lean lanes for documentation-only and npm-only changes, uses explicit suite
ownership for known paths, and fails closed for unknown ones. Focused Python
and Lean debug workflows provide
remote reproduction without rerunning unrelated matrices. On the measured
host, the resulting `make check` completed 256 selected tests in 8.36 seconds.

Source-to-suite impact is declared in `.github/ci-impact.json` and tested
against tracked source files. Unknown paths still fail closed. Each CI run
reports workflow elapsed time (the observable critical path), summed runner
minutes, and its longest job, making both reviewer latency and compute growth
visible. Scheduled lanes exercise repeated property tests, alternate orders,
optional providers, and the core performance benchmark outside the
pull-request critical path.

Do not run the complete non-Lean and Lean suites repeatedly during
implementation and then immediately repeat them in pull-request CI. Use
`make check` plus the affected focused target, and let CI provide one exhaustive
pass on the final tree. Run `make validate-full` locally only when CI is
unavailable or an environment-specific failure needs reproduction.

Some short CI jobs still overlap in setup or packaging work, but they run in
parallel and were not on the measured critical path. Consolidating them would
increase workflow coupling without materially shortening feedback, so this
audit leaves them unchanged.

An ephemeral timing artifact feeds `pytest-split`'s least-duration algorithm
for the four integration shards. Successful `main` runs publish fresh history;
missing or invalid history falls back to equal weighting. CI metrics report
max/min shard skew and flag ratios above 1.5x.

Do not stack a local duration refresh, full integration profiling, and focused
module debugging on the same host at once. That contention recreates the
pull-request wall-time problem the lane split exists to avoid: routine
`make check`, exhaustive merge-queue validation, and scheduled
stress/performance work must remain separate executions.

Portfolio smoke that constructs a full kernel lives under
`tests/integration/` rather than `tests/unit/`, so `make test-fast` stays free
of multi-second kernel startups. Modules that need authorized references opt
into `initialized_kernel_store_with_references` instead of rebuilding that
install on every case.

Attaching `JacobianKernel(tmp_path)` after the store fixture is intentional, not
a double bootstrap: the session template pays fresh construction once per worker,
`copytree` seeds each test root in milliseconds, and attach reuses content-
addressed descriptors in well under a second. Prefer the `kernel` /
`kernel_with_references` fixtures for that attach step; do not remove the store
fixtures to "avoid double construction."

Suite infrastructure checks for the store templates themselves also live under
`tests/integration/`: building and freezing those snapshots is multi-second
setup work and must not run in the routine fast lane.

Measured fixture anti-patterns that were fixed after the ownership merge:

- Plugin registry tests constructed `JacobianKernel(tmp_path / "state")` while
  the module fixture seeded `tmp_path`, so the template copy was unused. They
  now use a `plugin_kernel` fixture that copies the template into `state`.
- Finite-graph oracle cases paid a ~40s first-call Z3/solver startup on one
  parametrized node. Warmup now runs once inside the module-scoped
  `oracle_kernel` fixture; remaining cases stay sub-second to low single digits.
- SAT public reproductions and CLI enumeration that need authorized references
  seed from `initialized_kernel_store_with_references` instead of an empty
  root.
- Agent A/B and graph-shrinking cases that need a sibling state directory (not
  `tmp_path` itself) copy `kernel_store_template_with_references` into that
  directory instead of building an empty store and reinstalling references.
- Graph atlas search remains expensive (~90s measured) but already lives in
  the integration lane; no decorative `slow` marker was added until a suite
  actually excludes that marker.
- Graph counterexample shrinking and agent A/B scorers built kernels under
  `tmp_path / "state"` (or sibling roots) while the module fixture only seeded
  `tmp_path`, so template reuse never applied. Helpers now copy the reference
  template into those subdirectories before construction.
- On a quiet host after these moves, `make test-fast` completed 519 selected
  tests in about 19 seconds with no `JacobianKernel` constructions left under
  `tests/unit`, `tests/contract`, or `tests/checkers`.
