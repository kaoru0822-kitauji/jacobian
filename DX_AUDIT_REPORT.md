# Developer Experience Audit — Current Status

**Repository:** `/root/jacobian`
**Snapshot:** 2026-07-29
**Scope:** onboarding, CLI, Make targets, CI planning, test lanes, fixtures, and
developer tooling

This report replaces the earlier audit snapshots. Statuses below were checked
against the current source and tests after merging `origin/main`; old timings
are labelled as historical rather than presented as current measurements.

## Resolved findings

| Area | Current status | Evidence |
| --- | --- | --- |
| `jacobian init` output | **Resolved** | The default command prints a summary; `--json` retains the complete catalog. Covered by `tests/integration/infrastructure/test_cli.py`. |
| Documentation CI runner | **Resolved** | The docs job uses `ubuntu-latest`. |
| Scheduled stress lane | **Resolved** | `make test-stress` repeats the contract and checker suites, not only one property test. |
| Droid onboarding command | **Resolved** | `.factory/droids/jacobian-dev.md` uses `make validate-full`. |
| Pre-push scope | **Improved** | `make check` runs lint, mypy, and `test-unit-fast`; `pre-push-full` remains available for the broader core loop. |
| CI over-classification | **Improved** | `.github/ci-impact.json` gives documentation, pre-commit, duplicate-code, CI-script, and workflow changes narrower suite ownership. |
| Duration visibility | **Resolved** | Makefile pytest targets default to `--durations=10`; CI shards retain explicit duration output. |
| CI metrics critical path | **Resolved** | `ci-metrics` runs only on pushes to `main`. |
| Scheduled performance artifact | **Resolved** | Scheduled `main` runs compare against the previous successful benchmark and publish a report-only ±20% classification. |
| CI subprocess boilerplate | **Resolved** | `tests/helpers/ci.py` is shared by planner, validator, timing-manager, and timing-summary tests. |
| Subprocess marker | **Resolved** | `make test-subprocess` provides an explicit two-worker selection lane; the marker does not serialize unrelated xdist tests. |
| Completeness scope guard | **Resolved** | `test_exhaustive_result_without_scope_cannot_claim_complete_coverage` exercises COMPLETED + EXHAUSTIVE with no scope. |
| Coverage threshold | **Resolved** | The combined CI coverage job enforces 50%; producer jobs defer the check until data is combined. |
| Ruff version drift | **Resolved** | The dev dependency and pre-commit hook both pin Ruff 0.16.0. |

## Findings that remain

### P1 — Kernel startup is still the main structural cost

The historical controlled profile in
`docs/contributing/test-suite-cost-audit.md` measured roughly 13 seconds for a
fresh core kernel, 0.79 seconds to attach to a copied core snapshot, and 3.68
seconds to attach with authorized references. A current search finds 110 direct
`JacobianKernel(...)` constructions in tests, but that count includes deliberate
clean-store, provider, and fixture-behavior cases; it is not a list of 110 safe
replacements.

The next useful step is a repeatable profile by construction mode, followed by
targeted fixture conversion where the test does not intentionally exercise
bootstrap or restart behavior. Do not share mutable kernels across isolation
tests or weaken durable-store boundaries to improve this number.

### P1 — Descendant-written output still lacks a direct regression test

The bounded-process suite now covers clean worker output while a descendant
holds an inherited pipe, and it fails closed when a detached descendant keeps a
pipe open. The remaining proof gap is a descendant that writes bytes after the
worker exits: the test should establish whether those bytes are drained,
reported, or intentionally discarded, and should lock that behavior down.

### P2 — `validate-full` is broad local validation, not a CI reproduction

This is documented behavior, not a broken command. `make validate-full` omits
the separate Python 3.13 compatibility, combined coverage, security,
duplicate-code, npm, and deployment lanes. If maintainers want a local CI
reproduction, add a separately named target that composes those lanes; do not
make `validate-full` silently become an expensive, incomplete approximation of
CI.

## Audit rules

- Treat timings as host- and date-specific observations.
- Keep correctness gates separate from performance reports.
- Prefer behavioral regression tests over source-shape assertions.
- Preserve direct constructors and domain-owned helpers when they test a real
  isolation or semantic variation.
