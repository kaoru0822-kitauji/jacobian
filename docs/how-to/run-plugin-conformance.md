# Run the plugin conformance kit

[Documentation home](../index.md)

Run the conformance kit before treating a sealed plugin as compatible with the
provisional M3 runtime. The target must be disposable: several checks mutate
the package or create attack paths intentionally.

The kit enforces the plugin ownership boundary: a plugin may define
mathematical operations and required checker roles, but it cannot authorize
itself or widen the operator's execution and trust policy.

## Prepare the target

Install the plugin into a fresh `JacobianKernel`, create a minimal claim it can
search, and construct a `SyntheticPluginConformanceTarget` with:

- the kernel and installed plugin identifier;
- a bounded `SearchRunRequest`;
- the plugin entry-point file;
- a path and external target for the symlink-escape check; and
- an import marker that would reveal discovery-time execution.

The integration test
[`test_external_plugin_passes_the_generic_conformance_kit`][conformance-test]
is the executable example. It installs a synthetic third plugin without
changing the kernel or MCP adapter.

[conformance-test]: ../../tests/integration/test_plugin_registry_snapshots.py

## Run the checks

Use `require_plugin_conformance` when any failed check should fail the test:

```python
from jacobian.plugin_conformance import require_plugin_conformance


observations = require_plugin_conformance(target)
for observation in observations:
    print(observation.check.value, observation.passed, observation.detail)
```

Use `run_plugin_conformance` instead when a reporting tool needs all
observations without raising `PluginConformanceError`.

The target passes only when every standard observation passes. The matrix
covers successful execution, declared failure, malformed output, timeout,
path and symlink attacks, changed implementation bytes, unsupported evidence
promotion, and discovery without importing plugin code.

For target fields and exact pass conditions, consult the
[plugin conformance reference](../reference/plugin-conformance.md). The
[sealed plugin ADR](../explanation/adr/0002-sealed-plugin-packages.md) explains
why package identity and discovery are part of the trust boundary.
