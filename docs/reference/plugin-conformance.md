# Plugin conformance kit

[Documentation home](../index.md)

- Status: Provisional M3 implementation
- Python API: `jacobian.plugin_conformance`

The conformance kit tests whether an independently installed package crosses
Jacobian's registry, execution, search, and conjecture boundaries without core
or MCP changes. It is an executable extension gate, not a second unit-test
framework.

## Scope

The kit proves that:

- discovery and capability resolution use the sealed installed package;
- declared capabilities can complete one ordinary strategy search;
- failure, malformed output, and timeout remain operational states;
- traversal, symlink, and changed-byte attacks fail closed;
- an untrusted hypothesis transformer cannot promote evidence.

It does not prove that the plugin's mathematics is correct, that its search is
complete, or that installed code is safe for the host. Those properties require
domain tests, authorized checkers, and operator isolation policy.

## Disposable target package

Fault injection belongs in a separate conformance-only package installed into
isolated test state. Do not expose the conformance selector from a production
plugin.

The synthetic package declares ordinary `Proposer`, `Refiner`, `Evaluator`, and
`HypothesisTransformer` capabilities. Its proposer reads
`state["conformance_case"]` only inside this disposable package:

| Value | Required behavior |
| --- | --- |
| `execution-success` | Return a schema-valid finite proposal and complete normally |
| `declared-failure` | Raise a controlled error containing `declared plugin failure` |
| `malformed-output` | Return a non-object response |
| `timeout` | Remain active beyond the supplied wall budget |

The refiner and evaluator return valid ordinary contract responses. The
hypothesis transformer attempts a verified parameter-region label so the
workflow can demonstrate fail-closed rejection.

## Runner inputs

`SyntheticPluginConformanceTarget` requires:

- an isolated `JacobianKernel`;
- the installed synthetic plugin artifact URI;
- a valid base `SearchRunRequest`;
- the package implementation file to modify and restore;
- a disposable in-package symlink path and an outside target;
- optionally, an import marker written by the package's `__init__.py`.

The current interface is a Python operator/test API:

```python
from jacobian.plugin_conformance import (
    SyntheticPluginConformanceTarget,
    require_plugin_conformance,
)

target = SyntheticPluginConformanceTarget(
    kernel=kernel,
    plugin_id=plugin_id,
    search_request=request,
    implementation_file=package / "entry.py",
    symlink_path=package / "escape.py",
    symlink_target=outside_file,
    import_marker=import_marker,
)

observations = require_plugin_conformance(target)
```

The runner executes all checks and raises one `PluginConformanceError`
containing every failure. `run_plugin_conformance` returns the observations
without raising.

## Standard matrix

| Check | Boundary exercised | Passing result |
| --- | --- | --- |
| Execution success | Registry resolution and `SearchService` | Strategy completion with no verification promotion |
| Declared failure | Worker and search lifecycle | `ERROR` with the declared detail |
| Malformed output | Worker JSON boundary | `ERROR`; response is not accepted as a proposal |
| Timeout | Worker and durable budget | `TIMEOUT` with wall-limit stop reason |
| Path attack | Implementation registration | Traversal is rejected |
| Symlink attack | Whole-package measurement | Package symlink is rejected |
| Changed bytes | Capability resolution | Installed snapshot refuses changed source |
| Evidence promotion | `ConjectureService` | `ERROR`, no hypotheses, `UNVERIFIED` |

Each suite execution creates a fresh idempotency namespace. Repeated runs
therefore execute proposer, evaluator, and refiner code again instead of
returning earlier durable search results. The runner removes only the supplied
disposable import marker and symlink, and restores the implementation file
after the changed-byte check.

## Discovery without import

An import marker makes the no-import rule observable. Package installation and
capability resolution must leave the marker absent. The first successful worker
execution imports the package in its child process and creates the marker.

The registry measures all regular source files in the package, not just the
selected entrypoint file. A symlink anywhere in that measured package invalidates
resolution.

## Related decisions

- [Sealed package ADR](../explanation/adr/0002-sealed-plugin-packages.md)
- [Milestone 3 specification](milestones/m3-scalable-search.md)
- [Testing strategy](testing-strategy.md)
- [Threat model](../explanation/threat-model.md)
