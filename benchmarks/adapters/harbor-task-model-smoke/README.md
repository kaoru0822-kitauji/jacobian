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

The source metadata is a fixture for adapter plumbing, not a new benchmark
claim. `oracle-evidence.json` records the successful pinned Harbor Oracle run;
`parity-evidence.json` records the field-by-field comparison between the
generated manifest and the pinned Harbor task-model digest. Both files are
content-bound by `source.lock.json` and checked without network access.
