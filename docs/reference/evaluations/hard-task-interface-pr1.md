# Hard-task interface study PR1

This bounded study asks whether small Jacobian interface changes improve weak
Codex coordination on difficult tasks without changing the mathematics. The
frozen contract is
[`benchmarks/config/hard-task-interface-pr1.json`](../../../benchmarks/config/hard-task-interface-pr1.json).

The three tasks were already present at upstream revision
`7edc7ba9035e5f9de5a04f406cfe50e7da28d8e1`. Their Harbor task digests, model,
prompt, two-rollout count, timeout, metrics, invariants, and stop rules were
recorded before the baseline. Baseline and treatment each comprise six planned
rollouts in declared task order. A completed rollout is never retried merely
because its mathematical answer is rejected.

The host has no Docker-compatible runtime. The study therefore uses the locally
authenticated Codex CLI against an isolated public workspace and a local
Jacobian MCP server, then runs the unchanged task-owned verifier after model
exit. This is public host-local exploratory evidence, not a Harbor result and
not causal evidence.

Raw transcripts, MCP logs, isolated workspaces, verifier records, commands,
timestamps, and manifests are retained under
`benchmarks/results/hard-task-interface-pr1-{baseline,treatment}/`. The raw
result directories are intentionally not source-of-truth product contracts.

External design references are limited to current official documentation. MCP
recommends structured tool results and actionable tool-execution errors so a
model can self-correct; Anthropic recommends explicit relationships and strict
input/output descriptions in agent-facing tool contracts. These ideas may
motivate a candidate, but Jacobian trajectories and typed contracts decide what
is implemented.
