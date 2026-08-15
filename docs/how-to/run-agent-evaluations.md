# Run agent evaluations

[Documentation home](../index.md) · [Evaluation reference](../reference/evaluations/evaluation-methods.md)

Agent evaluations are explicit operator-run Harbor experiments. Freeze the
task, model, environment, budget, repetitions, and treatment definition before
running them. Compare a no-Jacobian control with a treatment exposing only the
public `math.find` and `math.run` surface; do not add a prescribed tool-call
sequence or server-side workflow.

Validate the selected task with its Harbor workflow before spending model or
Oracle resources. Publish results with task and environment digests, measured
outcomes, and limitations. The resulting logs and scores are evaluation data;
they do not create Jacobian artifacts, workspaces, or verification records.

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

`RUNTIME_SNAPSHOT` remains explicit: prepare a JSON record that freezes the
model and treatment condition, then pass its path to both `agent-eval` and
`agent-eval-validate`. The run binds the resolved image identity into that
record. Use `make eval-image-pull` to inspect or pre-pull the same immutable
image without starting a model run.

Harbor egress control shares the treatment services' network namespace, so
every Jacobian-enabled run reaches its local sidecar through
`http://127.0.0.1:8000/mcp`. This local endpoint is independent of upstream
egress. By default, Codex reaches its provider directly. Set
`JACOBIAN_EVAL_PROXY=1` only when the host requires a configured upstream HTTP,
HTTPS, or SOCKS proxy; it changes provider egress without changing the
Jacobian MCP endpoint. Proxy mode automatically resolves and mounts the
complete local standalone Codex runtime, including its Code Mode host; do not
mount the `codex` executable alone.
