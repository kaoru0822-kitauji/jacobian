# Canonical input and recovery study PR1

This bounded public observation tests two semantic tool changes on three existing
`symbolic-coordination-v1` tasks. The frozen contract is
[`benchmarks/config/canonical-input-recovery-pr1.json`](../../../benchmarks/config/canonical-input-recovery-pr1.json).

The primary outcome is unchanged task-owned exact verifier acceptance. Secondary
diagnostics count valid normalization or checker invocations, request-validation
failures, recovery after a rejected handoff, repeated calls, false certification,
and scope or completeness mistakes. Tool calls receive no reward.

The conditions are latest upstream, upstream plus exact canonical sparse-map input
normalization, and canonicalization plus typed recovery semantics. The third
condition and a recovery PR are conditional: they run only if the first two
conditions show a repeated recoverable handoff failure. Each active condition uses
three rollouts per task with Codex `gpt-5.4-mini`, medium reasoning, no web access,
no wrong-answer retries, and a 600-second timeout.

The host has no Docker-compatible runtime. Runs therefore use the locally
authenticated Codex CLI in isolated public workspaces against a local Jacobian MCP
server, followed by the unchanged clean-room verifier. They are host-local
exploratory observations, not Harbor executions or causal evidence. Raw commands,
timestamps, transcripts, MCP logs, workspaces, verifier records, and manifests are
saved under `benchmarks/results/canonical-input-recovery-pr1-*`.

The existing `polynomial-normalization` task is excluded. Its README declares
`verification_record_schema.json` agent-visible, but its environment Dockerfile
does not copy that file. That benchmark contract must be fixed separately before
the task can provide evidence for checker handoffs.
