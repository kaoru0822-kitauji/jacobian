# Architecture decision log

[Documentation home](../../index.md)

Architecture decision records preserve cross-cutting choices whose rationale
would otherwise be lost as the implementation changes. Each record states its
status. Acceptance records an architectural decision; it does not promise a
stable public contract.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-python-first-control-plane.md) | Use a Python-first control plane | Accepted |
| [0002](0002-sealed-plugin-packages.md) | Seal plugin packages and registry snapshots | Accepted, pre-stable |
| [0003](0003-durable-search-invocations.md) | Use SQLite acceptance with immutable search checkpoints | Accepted, pre-stable |
| [0004](0004-verified-parameter-regions.md) | Verify parameter regions through immutable subjects | Accepted, pre-stable |
| [0005](0005-direct-epistemic-workspaces.md) | Keep epistemic workspaces separate from capability assurance | Accepted, pre-stable |
| [0006](0006-semantic-test-topology.md) | Isolate tests by semantic depth and resource ownership | Accepted, pre-stable |
| [0007](0007-benchmark-and-package-layout.md) | Organize benchmarks by artifact class; package domain adapters without shims | Accepted, pre-stable |
| [0008](0008-harbor-native-benchmark-datasets.md) | Package every executable benchmark case in claim-specific Harbor datasets | Accepted, pre-stable |

Add an ADR when a decision changes a trust boundary, durable data model,
cross-component contract, dependency strategy, or other choice that would be
costly to reverse. Routine implementation details belong in code, tests, or a
how-to guide.

When a decision changes, preserve the old record and add a new ADR that marks
the earlier one as superseded. Do not silently rewrite an accepted decision to
describe a different architecture.

Related project-control documents:

- [Architecture](../architecture.md)
- [Product goals](../goals.md)
