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

There are two Harbor workflows. Use standalone observation to check whether an
agent can discover and use Jacobian. Use paired control/treatment jobs to ask
whether Jacobian changes outcomes.

### Standalone observation

Harbor runs the same canonical tasks with the local Jacobian MCP service as an
ordinary Compose sidecar:

```sh
export JACOBIAN_IMAGE='jacobian:local'
export JACOBIAN_MODEL='your-model'
make agent-eval DATASET=agent-workflow-v1 \
  JACOBIAN_ENABLED=1 EVAL_EXECUTE=1
```

The standalone observation job adds the Jacobian Compose sidecar and Harbor's
external MCP configuration. Task TOMLs remain agent-agnostic.

### Paired control/treatment evaluation

The control and treatment jobs use identical task bundles and task digests. The
only intended difference is Jacobian availability:

```sh
export JACOBIAN_MODEL='your-model'
export CODEX_FORCE_AUTH_JSON=1

# Control: no Jacobian sidecar and no MCP configuration.
make agent-eval DATASET=agent-workflow-v1 \
  JACOBIAN_ENABLED=0 TASKS=graph-counterexample EVAL_EXECUTE=1

# Treatment: Jacobian sidecar plus external MCP configuration.
export JACOBIAN_EVAL_HTTP_PROXY='http://host.docker.internal:7890'
export JACOBIAN_EVAL_HTTPS_PROXY='http://host.docker.internal:7890'
export JACOBIAN_EVAL_NO_PROXY='localhost,127.0.0.1,jacobian'
make agent-eval DATASET=agent-workflow-v1 \
  JACOBIAN_ENABLED=1 \
  TASKS=graph-counterexample EVAL_EXECUTE=1
```

`JACOBIAN_ENABLED=0` selects the control job; `JACOBIAN_ENABLED=1` selects the
treatment job and passes Harbor's supported `--mcp-config` option. Do not add
Jacobian to every task TOML for this comparison: that changes the task contract
and invalidates the matched boundary. Start with three representative cases and
three repetitions per condition; public-suite results remain workflow
observations, not held-out causal evidence.

The treatment Compose file defaults to `jacobian:local`; set `JACOBIAN_IMAGE`
when using another local or registry image. Both conditions use the shared
optional proxy overlay; only treatment adds the Jacobian service. Harbor selects tasks from the dataset
represented by the generated
`benchmarks/datasets/agent-workflow-v1/dataset.toml` manifest. Pass
`TASKS=graph-counterexample` selects the same small default explicitly; the
committed observation job defaults to that task.

The observation service is anonymous and intended for local evaluation. It
does not add an image identity, token, proxy, or eligibility preflight in front
of Harbor.

### Optional Docker proxy

The shared proxy Compose overlay leaves the task container's network direct by
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
workflow evidence, not a causal comparison: the public suite has no held-out
performance claim.

The separate
[`research-diagnostics-v1`](../../benchmarks/datasets/research-diagnostics-v1/README.md)
dataset is public and answer-visible. Its results remain case-level diagnostics
and must not be reported as held-out model performance.
