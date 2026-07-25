# Inspect, pause, and resume a search

[Documentation home](../index.md)

This guide covers the provisional M3 search runtime. Its commands and artifact
formats are outside v0.2 conformance and may change.

Use these commands when a `search-run` request has returned an experiment URI
and you need to inspect or control that experiment. Keep the same
`--state-dir` for every command; the state directory is the durable owner of
the experiment.

Set the values in your shell:

```sh
JACOBIAN_STATE=.jacobian
EXPERIMENT_URI='jacobian:experiment:replace-with-your-id'
```

Inspect the current snapshot:

```sh
uv run jacobian --state-dir "$JACOBIAN_STATE" \
  experiment-inspect "$EXPERIMENT_URI"
```

Pause a running experiment at its next checkpoint boundary:

```sh
uv run jacobian --state-dir "$JACOBIAN_STATE" \
  experiment-pause "$EXPERIMENT_URI"
```

Resume from the last committed checkpoint:

```sh
uv run jacobian --state-dir "$JACOBIAN_STATE" \
  experiment-resume "$EXPERIMENT_URI"
```

Wait for a terminal or paused snapshot:

```sh
uv run jacobian --state-dir "$JACOBIAN_STATE" \
  experiment-wait "$EXPERIMENT_URI" --timeout-seconds 30
```

If the process was lost, create a new Jacobian process against the same state
directory and inspect the experiment before resuming it. Recovery uses the
accepted request, append-only lifecycle events, and the last immutable
checkpoint; it does not depend on chat history.

One process must own a state directory at a time. The current implementation
does not provide a distributed lease or queue, so do not point concurrent
Jacobian processes at the same directory.

See [Durable search runtime](../explanation/search-runtime.md) for the
checkpoint and recovery model, and
[M3 scalable search](../reference/milestones/m3-scalable-search.md) for the
provisional contract.
