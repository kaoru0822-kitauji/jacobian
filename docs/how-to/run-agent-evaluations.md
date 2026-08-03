# Run agent evaluations

[Documentation home](../index.md) · [Evaluation reference](../reference/agent-evaluations.md)

This guide covers an explicit operator-run of Harbor workflow observations and
paired Jacobian control/treatment runs. Model execution is not a routine
development or pull-request gate. The evaluation roles, assurance rules, and
interpretation boundaries are in the [reference page](../reference/agent-evaluations.md).

## Validate the dataset

Run the exact selected-task contract checks before spending model or Docker
time:

```sh
make harbor-check-task DATASET=agent-workflow-v1 TASKS="graph-counterexample"
make harbor-oracle-task DATASET=agent-workflow-v1 TASKS="graph-counterexample"
```

Use the full `make harbor-check` and explicitly scoped `make harbor-oracle`
paths only for shared Harbor tooling, schemas, registry, suite policy, or
other control-plane changes. Pass `TASKS="..."` for a bounded dataset Oracle;
pass `FULL=1` only when a complete dataset sweep is intentional.

## Set shared run conditions

For a paired comparison, set the same model, authentication, task filter,
prompt, budget, and environment before running either condition:

```sh
export JACOBIAN_MODEL='your-model'
export CODEX_FORCE_AUTH_JSON=1
```

The checked-in agent-workflow observation jobs deliberately do not attach a
host-proxy overlay. Their selected task environments use Harbor's
`no-network` policy; Jacobian is an internal Compose service reached only over
loopback in the shared egress-control namespace. Use a pre-provisioned agent
runtime when the agent itself must also remain offline. Stock Harbor Codex
setup installs missing packages and the CLI from the network, so it cannot
start in these tasks without an explicitly networked agent phase.

## Run with Jacobian

The local path uses Harbor's Docker environment, a Jacobian Compose sidecar,
and Harbor's external MCP configuration. The default sidecar image is
`jacobian:local`.

```sh
export JACOBIAN_IMAGE='jacobian:local'

make agent-eval DATASET=agent-workflow-v1 \
  JACOBIAN_ENABLED=1 EVAL_EXECUTE=1
```

Use `TASKS=graph-counterexample` for a small smoke run. The treatment run uses
`benchmarks/config/jacobian.mcp.json`; task TOMLs remain agent-agnostic.

## Run without Jacobian

Use the same shared run conditions:

```sh
make agent-eval DATASET=agent-workflow-v1 \
  JACOBIAN_ENABLED=0 \
  TASKS=graph-counterexample EVAL_EXECUTE=1
```

`JACOBIAN_ENABLED=0` selects the control job without the Jacobian sidecar or
MCP configuration. `JACOBIAN_ENABLED=1` selects the treatment job and passes
Harbor's `--mcp-config` option.

The treatment Compose file adds a Docker healthcheck that runs Jacobian's
MCP-level readiness probe. Harbor waits for `service_healthy` before starting
`main`; the probe validates the MCP tools and required capability over
`127.0.0.1:8000` without opening external networking.

## Docker and Daytona

The checked-in Jacobian evaluation jobs use Docker Compose because Harbor's
local multi-container path needs the `main` container and Jacobian sidecar on
the same network. Daytona is a separate remote execution option and is not
selected by these Makefile commands.

The local image name `jacobian:local` is not pullable by a remote Daytona
worker. A Daytona run therefore needs a published, immutable Jacobian image in
a registry that the worker can access, plus a reachable MCP endpoint or a
Daytona-compatible sidecar configuration. Do not compare a Docker control run
with a Daytona treatment run unless the runtime, image, network, and resource
limits are otherwise held constant.

## Inspect results

Harbor writes results under `benchmarks/results/`. Inspect the summary with:

```sh
uvx --from harbor==0.20.0 harbor view \
  benchmarks/results/agent-workflow-v1
```

For Jacobian treatment runs, inspect Harbor ATIF together with Jacobian
telemetry. Check capability discovery and descriptions, invocation and
parameter errors, artifact and verification-record flow, repeated or
irrelevant calls, shell/file activity, tokens, time, and completion.

Record the git tree, task digests, provider/runtime, model and prompt settings,
raw trace location, and validation actually run. A public workflow result is
regression or observation evidence; it is not held-out causal evidence.

## Troubleshooting

If the command exits with `JACOBIAN_MODEL must be exported`, export the model
before invoking Make:

```sh
export JACOBIAN_MODEL='your-model'
```

If the run stalls at `starting environment`, Docker may be building the task
image or waiting on the Jacobian healthcheck. Check the Docker Compose logs and
confirm that the selected image contains `jacobian.adapters.mcp.readiness`.

If the treatment agent reports no Jacobian tools, confirm that
`JACOBIAN_ENABLED=1` is set and that the treatment job includes the external
MCP configuration. If the agent cannot reach the sidecar, inspect the Compose
network and ensure the sidecar is listening on `0.0.0.0:8000`.
