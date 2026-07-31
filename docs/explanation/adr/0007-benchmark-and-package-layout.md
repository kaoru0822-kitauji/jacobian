# ADR 0007: Benchmark layout and domain package boundaries

[Documentation home](../../index.md) · [Decision log](index.md)

- Status: Accepted for the pre-stable architecture; benchmark layout
  superseded by [ADR 0008](0008-harbor-native-benchmark-datasets.md)
- Date: 2026-07-31

## Decision

### Benchmark tree

Organize `benchmarks/` by **artifact class**, not by historical drop order:

- `regression-v1/` — frozen Harbor dataset path (Oracle + observation)
- `research/` — public challenge corpus and runner
- `reproductions/` — public fixture JSON for tests
- `examples/` — pilot cases
- `performance/` — operational microbenchmarks
- `provider_spikes/` — optional backend feasibility work

Harbor `regression-v1` remains path-stable. All other classes may move only
with full call-site cleanup in the same change: no re-export shims and no dual
homes for the migrated paths.

Provider spikes are contributing evidence, not product surface. They must not
import into portfolio installation.

### Package layout

- New mathematical producers land under `src/jacobian/domains/<domain>/` as
  `DomainBundle` units.
- Large root-level adapter clusters are split into packages with install
  entrypoints used by `portfolio/`, deleting the former root module in the
  same change (no re-export shims):
  - `jacobian.polynomials`
  - `jacobian.graphs`
  - `jacobian.matrices`
  - `jacobian.lean_frontend`
  - `jacobian.sat_smt`
- Kernel services are packages with `service.py` + focused helpers:
  - `jacobian.search`
  - `jacobian.experiments`
  - `jacobian.workspaces`
  - `jacobian.verification`
- Agent-evaluation helpers that are not Harbor tasks live under
  `jacobian.eval` (telemetry, independent oracles). Runtime
  `EvaluationService` stays with kernel services; it is not Harbor tooling.

## Consequences

- Docs, skills, Makefile, CI, and tests must name the class directories
  explicitly.
- Status overlays for research challenges may update live path fields when
  the corpus moves; immutable suite **content digests** remain the binding.
- Refactors that relocate modules must leave no import or filesystem alias at
  the old path.
