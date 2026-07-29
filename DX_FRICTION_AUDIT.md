# Developer Friction Audit — Current Measurements and Actions

**Repository:** `/root/jacobian`
**Snapshot:** 2026-07-29
**Audience:** contributors deciding which validation to run locally and which
work belongs in CI

This is the operational companion to `DX_AUDIT_REPORT.md`. It records the
current lane design and separates measured observations from follow-up work.

## Current lane design

| Lane | What it does | Policy |
| --- | --- | --- |
| `make check` | Ruff, strict typing, and the unit-only fast loop | Routine pre-push gate |
| `make pre-push-full` | Routine checks plus the sequential core suites | Opt-in local validation |
| `make test-core` | Core directories under capped xdist | Parallel core validation |
| `make test-integration` | Integration and end-to-end directories under capped xdist | CI-aligned boundary validation |
| `make test-subprocess` | Tests selected by `pytest.mark.subprocess`, capped at two workers | Opt-in clean-process lane |
| Scheduled `performance` | Pyperf benchmark plus comparison with the prior successful `main` artifact | Report-only observability |

All Makefile pytest targets emit their ten slowest tests by default. CI timing
history is an ephemeral scheduling hint; missing or invalid history falls back
to equal-weight sharding.

## Cost model

The durable kernel is intentionally real: capability registration, schema
validation, artifact identity, SQLite writes, checker authorization, and
process boundaries are part of the product contract. The historical profile in
`docs/contributing/test-suite-cost-audit.md` measured fresh construction at
about 13 seconds, copied-store attachment at 0.79 seconds, and copied-store
attachment with references at 3.68 seconds.

That makes fixture choice the highest-value local optimization. Use
`kernel`/`kernel_with_references` when the test needs an isolated seeded store;
retain direct `JacobianKernel(...)` construction when the test is specifically
checking bootstrap, restart, provider availability, or fixture mechanics.

## Follow-up queue

1. Profile kernel construction by mode on a quiet host and convert only the
   direct constructions that do not test initialization semantics.
2. Add a regression test for bytes written by a descendant after the worker
   exits, closing the remaining bounded-pipe evidence gap.
3. Decide whether a separately named `validate-ci` composition target is worth
   maintaining. Keep `validate-full` honest about its intentionally omitted CI
   lanes.

## Evidence hygiene

The previous friction snapshot mixed resolved findings, historical timings, and
new proposals in one priority list. This revision marks resolved work above,
keeps measurements tied to their source audit, and leaves only actions that
still require engineering or a maintainer decision.
