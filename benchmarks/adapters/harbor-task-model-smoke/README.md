# Harbor task-model smoke adapter

This is a deliberately small, offline adapter fixture. It records one frozen
source row and deterministically emits a reference to the existing
`agent-workflow-v1/graph-counterexample` task. The generator does not copy or
modify the task; Harbor's pinned `Task` model remains the authority for its
content digest.

Run the complete contract and regeneration checks with:

```sh
make harbor-adapter-check ADAPTER=harbor-task-model-smoke
```

The source metadata is a fixture for adapter plumbing, not a benchmark result.
Oracle and parity evidence are the checked-in digests below, so the adapter can
be validated without network access or a mutable source checkout.
