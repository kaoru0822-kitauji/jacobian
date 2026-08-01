# Agent workflow observations

[Documentation home](../index.md)

Jacobian's fixed workflow observation surface is the Harbor
[`agent-workflow-v1`](../../benchmarks/datasets/agent-workflow-v1/README.md)
dataset. Its self-contained mathematical tasks cover graph, algebra,
linear-algebra, number-theory, geometry, combinatorics, probability, and
formal-mathematics workflows, including the original graph, partition, SAT,
linear-system, Hermite, and polynomial cases.

The task bundles are agent-agnostic. Instructions describe the mathematical
outcome and evidence without naming capability IDs or prescribing
decomposition, verification order, or stopping criteria. Each task freezes its
offline input, Oracle-only solution, and separate clean-room verifier.

## Validation boundary

Task and verifier validation is separate from model observation:

```sh
make harbor-check
make harbor-oracle DATASET=agent-workflow-v1
```

The suite module checks that each member ID names a direct Harbor task bundle
and validates the generated task digests. Wrong
answers, malformed or escaped evidence, incomplete scope, and false
certification receive zero reward.

## Jacobian observation

Harbor runs the same canonical tasks with the local Jacobian MCP service as an
ordinary Compose sidecar:

```sh
export JACOBIAN_IMAGE='jacobian:local'
export JACOBIAN_MODEL='your-model'
make agent-eval DATASET=agent-workflow-v1 EVAL_EXECUTE=1
```

The Compose file defaults to `jacobian:local`; set `JACOBIAN_IMAGE` when using
another local or registry image. Harbor selects tasks from the dataset
represented by the generated
`benchmarks/datasets/agent-workflow-v1/dataset.toml` manifest. Pass
`TASKS=graph-counterexample` selects the same small default explicitly; the
committed observation job defaults to that task.

The observation service is anonymous and intended for local evaluation. It
does not add an image identity, token, proxy, or eligibility preflight in front
of Harbor.

### Optional Docker proxy

The observation Compose overlay leaves the task container's network direct by
default. If the host requires a proxy for package installation or Codex model
access, configure it explicitly for the container:

```sh
export JACOBIAN_EVAL_HTTP_PROXY='http://host.docker.internal:7890'
export JACOBIAN_EVAL_HTTPS_PROXY='http://host.docker.internal:7890'
export JACOBIAN_EVAL_NO_PROXY='localhost,127.0.0.1,jacobian'
make agent-eval DATASET=agent-workflow-v1 TASKS=graph-counterexample EVAL_EXECUTE=1
```

The overlay maps `host.docker.internal` to the Docker host and passes both
upper- and lower-case proxy variables to Harbor's `main` container, including
the agent installation phase. Proxying remains disabled when these variables
are unset. On Linux, the host proxy must accept connections from Docker's
bridge interface; a proxy bound only to the host's loopback address is not
reachable from a container.

Inspect Harbor ATIF together with Jacobian telemetry for discovery,
descriptions, invocation and parameter errors, artifact and verification-record
flow, repeated calls, shell activity, tokens, time, and completion. This is
workflow evidence, not a causal comparison: version 1 has no control condition,
randomized pairing, or held-out performance claim.

The separate
[`research-diagnostics-v1`](../../benchmarks/datasets/research-diagnostics-v1/README.md)
dataset is public and answer-visible. Its results remain case-level diagnostics
and must not be reported as held-out model performance.
