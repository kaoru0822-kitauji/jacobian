# Architecture decision log

[Documentation home](../../index.md)

Architecture decision records preserve cross-cutting choices whose rationale
would otherwise be lost as the implementation changes. Each record states its
status and release scope; an accepted provisional decision does not extend the
v0.2 public contract.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-python-first-control-plane.md) | Use a Python-first control plane | Accepted for v0.2 |
| [0002](0002-sealed-plugin-packages.md) | Seal plugin packages and registry snapshots | Accepted for the provisional M3 implementation |
| [0003](0003-durable-search-invocations.md) | Use SQLite acceptance with immutable search checkpoints | Accepted for the provisional M3 implementation |
| [0004](0004-verified-parameter-regions.md) | Verify parameter regions through immutable subjects | Accepted for the provisional M4 implementation |

Add an ADR when a decision changes a trust boundary, durable data model,
cross-component contract, dependency strategy, or other choice that would be
costly to reverse. Routine implementation details belong in code, tests, or a
how-to guide.

When a decision changes, preserve the old record and add a new ADR that marks
the earlier one as superseded. Do not silently rewrite an accepted decision to
describe a different architecture.

Related project-control documents:

- [Architecture](../architecture.md)
- [Roadmap](../roadmap.md)
- [Threat model](../threat-model.md)
