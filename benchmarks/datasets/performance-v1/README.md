# Jacobian performance-v1 historical baseline

This dataset records controlled operational measurements for four existing
Jacobian benchmark entry points. Its Oracle jobs run the fixed drivers and
publish raw pyperf-compatible JSON plus environment metadata.

`performance-v1` is intentionally a historical baseline, not a current-main
benchmark. Every task runs Jacobian revision
`6fd5fc5df6bc49f230484bc5c78cbd365941c78c` (`0.6.0-alpha.0`) with MCP
`2.0.0b2` and uv `0.8.4`. The machine-readable identity is in
[`baseline.toml`](baseline.toml), and repository tests require every task input
and environment to agree with it. A current-main measurement must be published
as a new versioned dataset rather than moving this baseline in place.

Reward covers only task-contract validity, evidence integrity, and successful
measurement. Timing values are report-only: they are not mathematical
correctness evidence, service-level objectives, or agent-performance
measurements. Scheduled runs use the Oracle so model latency cannot be
misreported as Jacobian runtime latency.

Run `make performance-eval`. The generated Harbor manifest is owned by
`suite.toml` and the task contents; do not edit its digests directly.
