# Jacobian documentation

Jacobian's documentation is organized by what the reader is trying to do.
Start with a tutorial when learning the system, use a how-to guide for a
specific task, consult reference material for exact contracts, and read the
explanations for design rationale.

Jacobian exposes composable mathematical capabilities through an MCP server,
CLI, and Python library. Capabilities have mathematically atomic,
agent-visible outcomes; agents compose them into research strategies. Optional
workflows preserve intermediate artifacts, and only operator-authorized
independent checkers may promote exact evidence to a verified result. The
[product model](explanation/product-blueprint.md) defines the capability
contract and ownership boundaries.

The API and artifact formats are pre-stable. Experimental and
version-breaking adapters may be exposed before held-out evaluations show
lift. Evaluations guide portfolio behavior and maintenance; they do not grant
verification authority. Release specifications describe supported snapshots,
not a required order of development.

## Project control documents

These documents track the design while the public API and artifact formats are
still pre-stable:

| Question | Document | Status |
| --- | --- | --- |
| What product is Jacobian building? | [Product model](explanation/product-blueprint.md) | Active product direction |
| What does the system currently look like? | [Architecture](explanation/architecture.md) | Current implementation and trust boundaries |
| What direction is the project taking? | [Product goals](explanation/goals.md) | Rolling goals pursued in parallel |
| Why were cross-cutting choices made? | [Architecture decision log](explanation/adr/index.md) | Accepted decisions with release scope |
| Which properties and trust boundaries must hold? | [Threat model](explanation/threat-model.md) | Current protected properties and exclusions |
| What is the supported release contract? | [v0.2 specification](reference/specifications/v0.2.md) and [conformance gate](reference/conformance-v0.2.md) | Normative for `0.2.0a0` |

## Tutorials

Tutorials are guided learning paths. They assume no prior Jacobian experience
and build toward a complete result.

- [Find and verify a counterexample](tutorials/first-verified-result.md) shows
  the boundary between an unverified evaluator result and independently
  verified evidence.

## How-to guides

How-to guides assume you already understand Jacobian's basic model and need to
complete a specific task.

- [Deploy the remote MCP server](how-to/deploy-remote-mcp.md)

## Reference

Reference documents define exact interfaces, records, gates, and test
expectations.

- [Tool surface](reference/tools.md)
- [Provider runtime contract](reference/provider-runtime.md)
- [v0.2 specification](reference/specifications/v0.2.md)
- [v0.2 conformance specification](reference/conformance-v0.2.md)
- [Plugin conformance contract](reference/plugin-conformance.md)
- [Mathematical scenario catalog](reference/math-scenarios.md)
- [Reference benchmarks](reference/benchmarks.md)
- [Performance benchmark protocol](reference/performance-benchmarks.md)
- [Testing strategy](reference/testing-strategy.md)
- [Agent evaluation protocol](reference/agent-evaluations.md)
- [Capability workflow evaluation plan](reference/capability-workflow-evaluations.md)

## Explanation

Explanation documents describe why Jacobian has its current boundaries and
how its major parts fit together.

- [Architecture](explanation/architecture.md)
- [Product model](explanation/product-blueprint.md)
- [Threat model](explanation/threat-model.md)
- [Product goals](explanation/goals.md)
- [Durable search runtime](explanation/search-runtime.md)
- [Architecture decision log](explanation/adr/index.md)
- [ADR 0001: Python-first control plane](explanation/adr/0001-python-first-control-plane.md)
- [ADR 0002: Sealed plugin packages](explanation/adr/0002-sealed-plugin-packages.md)
- [ADR 0003: Durable search invocations](explanation/adr/0003-durable-search-invocations.md)
- [ADR 0004: Verified parameter regions](explanation/adr/0004-verified-parameter-regions.md)

## Contributing

Read [CONTRIBUTING.md](../CONTRIBUTING.md) before changing code or public
documentation. The [issue index](contributing/issues.md) records implementation
work that has been identified but not necessarily scheduled. The
[atomic capability portfolio](contributing/atomic-capability-portfolio.md)
records the formal-first backend research, ordering, installation tradeoffs,
and evaluation gates used to decide which mathematical slices to build next.

When adding a document, place it according to the reader's need:

- `tutorials/` for a guided learning experience;
- `how-to/` for completing one task;
- `reference/` for contracts and lookup material;
- `explanation/` for design context and decisions; and
- `contributing/` for maintainer-facing research and planning records.

Do not mix active direction with supported behavior. Product goals guide
priorities; only an applicable specification or conformance document defines a
release contract.
