# Capability example coverage report

Generate the report from the installed catalog with:

```sh
make example-coverage
```

This writes JSON and Markdown files under `reports/` by default. Counts and
capability IDs come from `JacobianKernel.capabilities.catalog()`; the report is
not a second descriptor or example registry. Use `--json` and `--markdown` on
the script to choose different output paths.

## Interpretation

- **Directly invocable** means the request schema does not contain artifact,
  checker, proof-state, plugin, experiment, workspace, session, or URI inputs,
  and the provider/capability is not runtime-labelled by the report heuristic.
- **Artifact-dependent** identifies requests that need runtime artifacts or
  URIs. These are not expected to have standalone examples without a stable
  fixture.
- **Runtime/plugin dependent** is a triage category for Lean, solver/backend,
  plugin, or runtime-labelled providers, IDs, and tags; it is not an assurance
  claim.
- **Schema-valid** means each example input validates against its descriptor's
  canonical input schema. It does not imply execution success or verification.
- **Integration-test evidence** is best-effort text evidence from searching
  `tests/integration` for the capability ID. Missing evidence needs review and
  is not proof that no test exists.
- **Known exclusions** are conservative artifact/runtime categories. The tool
  does not generate examples or alter descriptors.

Regenerate after changing capability registration, schemas, or invocation
examples. The generated snapshot can be committed separately if maintainers
want a versioned report; the source of truth remains the installed catalog.
