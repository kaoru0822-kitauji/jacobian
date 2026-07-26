# Test-suite cost audit

[Documentation home](../index.md)

This audit records the 2026-07-26 local measurements used to restore a short
edit-test loop without weakening Jacobian's verification boundary. Timings are
machine-local observations, not performance gates.

## Measured lanes

| Lane | Selected tests | Observed wall time | Purpose |
| --- | ---: | ---: | --- |
| Unfiltered `uv run pytest` | 546 | 372.48 s | Diagnostic baseline; mixes Lean into the general xdist pool |
| `make test-fast`, before this audit | 246 | 43.92 s | Non-integration edit loop |
| `make test-fast`, after fixture reuse | 246 | 6.55 s | Non-integration edit loop |
| Integration, excluding end-to-end and Lean | 275 | 218.88 s | Real stores, subprocesses, adapters, and capability composition |
| End-to-end | 5 | 33.84 s | Distinct complete mathematical workflows |
| `make test-lean` | 20 | 218.26 s | Serial pinned Lean and Mathlib coverage |
| Non-Lean duration calibration | 526 | 285.13 s | Refresh data for CI shard assignment |

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

CI requested `pytest-split`'s `least_duration` algorithm, but
`.test_durations` was ignored. A fresh checkout therefore had no timings and
fell back to an even test-count split. The measured non-Lean durations are now
committed. At capture time the two CI groups each contained 263 tests with the
same 558-second estimated serial cost.

## Development policy

Use the cheapest lane that preserves the boundary being changed:

```sh
make test-fast
make test TESTS=tests/integration/test_mcp_adapter.py
make test
make test-lean
make validate-full
```

`make test-fast` is the normal edit loop. Use focused integration tests while
changing stores, adapters, plugins, subprocesses, or checker execution.
`make test` runs the complete non-Lean suite, and `make test-lean` keeps the
memory-heavy backend serial. Neither is a routine pre-push requirement:
`make check` is the local handoff gate, and CI owns exhaustive validation.
`make validate-full` exists only to reproduce that exhaustive validation when
CI is unavailable or an environment-specific failure requires it. Do not use
unfiltered `uv run pytest` as the default handoff command because it mixes Lean
into the general parallel pool.

Recent CI phase timing supports retaining two independent Lean shards. On both
lanes, Lean toolchain and Mathlib cache setup took about 83 to 85 seconds,
`lake build repl` took 11 to 12 seconds, and selected tests took 66 to 71
seconds. Sharing Jacobian's build output would serialize both shards behind a
new preparation job to avoid only the small build phase, so CI keeps the build
local to each parallel lane. The workflow records these phases for future
decisions.

Refresh CI timings after a material suite expansion or when shard runtimes
diverge:

```sh
make test-durations
```

Review and commit the resulting `.test_durations` change with the tests that
caused it. Ordinary test edits do not need a refresh.

## Follow-up opportunities

- Profile kernel startup as a product concern before changing its durability
  or registration model.
- Reuse module fixtures only where inputs remain isolated and the shared state
  is immutable.
- Track lane wall times periodically; investigate changes before adding a
  blanket `slow` marker or weakening required coverage.
- Move backend combinations to a slower lane only when the pull-request lane
  still exercises every affected trust boundary.
