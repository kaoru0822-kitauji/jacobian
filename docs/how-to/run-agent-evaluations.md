# Run agent observations

[Documentation home](../index.md) · [Evaluation reference](../reference/evaluations/evaluation-methods.md)

Use Harbor to see how an agent performs on a bounded mathematical task with the
public Jacobian tools available. A normal run is an observation: Harbor records
the resolved configuration and task digest in `config.json` and `lock.json`,
then retains the trajectory, verifier reward, submitted artifacts, and the
Jacobian MCP log. Review the resulting job directory with `harbor view`.

Run the task's exact Oracle once before using a new or changed benchmark, then
launch any number of model observations against that fixed task:

```sh
JACOBIAN_MODEL=gpt-5.6-luna make agent-eval \
  DATASET=mathematical-benchmarks-v1 TASKS=graph-counterexample \
  EVAL_EXECUTE=1 EVAL_ATTEMPTS=1 EVAL_REASONING_EFFORT=high
```

Set `EVAL_ATTEMPTS` for repeated rollouts. `EVAL_ARGS` remains available for
Harbor options such as a job name or a separate results directory, but no
hand-authored runtime snapshot is required for an ordinary observation.

Run each arm in a fresh temporary `CODEX_HOME`, never through direct host `codex exec`.
The control must have no Jacobian MCP server; the treatment must expose only the
intended Jacobian MCP configuration and no Jacobian Skill.

For a Jacobian-enabled `make agent-eval` run, omit `JACOBIAN_IMAGE`. The target
then resolves the current clean revision to the immutable
`ghcr.io/morluto/jacobian@sha256:...` image before Harbor starts the sidecar.
An explicit `JACOBIAN_IMAGE` is an override for a deliberately frozen run, so
do not point it at a convenience or stale local tag. A dirty checkout instead
builds `jacobian:local`; it is useful for local diagnostics but cannot support
reproducible treatment evidence.

For a comparative claim, run matched control and treatment conditions and use
the stricter normalization and comparison workflow. Freeze a snapshot only at
an intentional publication or comparison boundary; it is not a prerequisite
for exploring model behavior or reviewing a Harbor run. Use
`make eval-image-pull` to inspect or pre-pull the treatment image without
starting a model run.

Harbor egress control shares the treatment services' network namespace, so
every Jacobian-enabled run reaches its local sidecar through
`http://127.0.0.1:8000/mcp`. This local endpoint is independent of upstream
egress. By default, Codex reaches its provider directly. Set
`JACOBIAN_EVAL_PROXY=1` only when the host requires a configured upstream HTTP,
HTTPS, or SOCKS proxy; it changes provider egress without changing the
Jacobian MCP endpoint. Proxy mode automatically resolves and mounts the
complete local standalone Codex runtime, including its Code Mode host; do not
mount the `codex` executable alone.
