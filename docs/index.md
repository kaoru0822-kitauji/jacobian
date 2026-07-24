# Jacobian documentation

Jacobian's documentation is organized by what the reader is trying to do.
Start with a tutorial when learning the system, use a how-to guide for a
specific task, consult reference material for exact contracts, and read the
explanations for design rationale.

The only current release contract is v0.2 alpha. Documents for M3, M4, M5, and
v1.0 describe provisional or planned work unless they explicitly say
otherwise.

## Project control documents

These documents track the design while the public API and artifact formats are
still pre-stable:

| Question | Document | Status |
| --- | --- | --- |
| What does the system currently look like? | [Architecture](explanation/architecture.md) | Current v0.2 design plus labeled provisional M3/M4 sections |
| What is implemented, provisional, or planned? | [Roadmap](explanation/roadmap.md) | Active milestone plan; gates are not promised release dates |
| Why were cross-cutting choices made? | [Architecture decision log](explanation/adr/index.md) | Accepted decisions with release scope |
| Which properties and trust boundaries must hold? | [Threat model](explanation/threat-model.md) | Current for v0.2 and provisional M3/M4 code |
| What is the supported release contract? | [v0.2 specification](reference/specifications/v0.2.md) and [conformance gate](reference/conformance-v0.2.md) | Normative for `0.2.0a0` |
| Which later contracts are being exercised? | [M3](reference/milestones/m3-scalable-search.md) and [M4](reference/milestones/m4-conjecture-workflows.md) | Provisional; outside v0.2 conformance |

## Tutorials

Tutorials are guided learning paths. They assume no prior Jacobian experience
and build toward a complete result.

- [Find and verify a counterexample](tutorials/first-verified-result.md) shows
  the boundary between an unverified evaluator result and independently
  verified evidence.

## How-to guides

How-to guides assume you already understand Jacobian's basic model and need to
complete a specific task.

- [Inspect, pause, and resume a search](how-to/resume-search.md)
- [Run the plugin conformance kit](how-to/run-plugin-conformance.md)

## Reference

Reference documents define exact interfaces, records, gates, and test
expectations.

- [Tool surface](reference/tools.md)
- [v0.2 specification](reference/specifications/v0.2.md)
- [v0.2 conformance specification](reference/conformance-v0.2.md)
- [Plugin conformance contract](reference/plugin-conformance.md)
- [Mathematical scenario catalog](reference/math-scenarios.md)
- [Reference benchmarks](reference/benchmarks.md)
- [Performance benchmark protocol](reference/performance-benchmarks.md)
- [Testing strategy](reference/testing-strategy.md)
- [Agent evaluation protocol](reference/agent-evaluations.md)

Later-release contracts are provisional:

- [M3 scalable search](reference/milestones/m3-scalable-search.md)
- [M4 conjecture workflows](reference/milestones/m4-conjecture-workflows.md)
- [M5 research corpus integration](reference/milestones/m5-research-corpus.md)
- [v1.0 stability target](reference/specifications/v1.0.md)

## Explanation

Explanation documents describe why Jacobian has its current boundaries and
how its major parts fit together.

- [Architecture](explanation/architecture.md)
- [Threat model](explanation/threat-model.md)
- [Roadmap](explanation/roadmap.md)
- [Durable search runtime](explanation/search-runtime.md)
- [Architecture decision log](explanation/adr/index.md)
- [ADR 0001: Python-first control plane](explanation/adr/0001-python-first-control-plane.md)
- [ADR 0002: Sealed plugin packages](explanation/adr/0002-sealed-plugin-packages.md)
- [ADR 0003: Durable search invocations](explanation/adr/0003-durable-search-invocations.md)
- [ADR 0004: Verified parameter regions](explanation/adr/0004-verified-parameter-regions.md)

## Contributing

Read [CONTRIBUTING.md](../CONTRIBUTING.md) before changing code or public
documentation. The [issue index](contributing/issues.md) records implementation
work that has been identified but not necessarily scheduled.

When adding a document, place it according to the reader's need:

- `tutorials/` for a guided learning experience;
- `how-to/` for completing one task;
- `reference/` for contracts and lookup material;
- `explanation/` for design context and decisions.

Do not mix release status. A v0.2 document is normative only when the v0.2
specification or conformance document says so; milestone documents remain
provisional until their release is declared.
