# Jacobian performance-v1

This dataset records controlled operational measurements for four existing
Jacobian benchmark entry points. Its Oracle jobs run the fixed drivers and
publish raw pyperf-compatible JSON plus environment metadata.

Reward covers only task-contract validity, evidence integrity, and successful
measurement. Timing values are report-only: they are not mathematical
correctness evidence, service-level objectives, or agent-performance
measurements. Scheduled runs use the Oracle so model latency cannot be
misreported as Jacobian runtime latency.

Run `make performance-eval`. The generated Harbor manifest is owned by
`suite.toml` and the task contents; do not edit its digests directly.
