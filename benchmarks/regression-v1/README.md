# Jacobian regression-v1

This is the small committed Harbor dataset for observing Jacobian-enabled
mathematical workflows. It contains eight self-contained, answerable tasks;
the task digests in `dataset.toml` are the task identities.

The tasks are agent-agnostic. Their instructions name no tool, capability, or
invocation order. Each task has an offline input, schema 1.4 metadata, an
Oracle-only solution, and a separate clean-room verifier. The verifier reports
`correctness`,
`evidence_validity`, `scope_accuracy`, `assurance_calibration`, and the
weighted `reward`; a wrong result or an unsupported `VERIFIED` claim forces the
aggregate reward to zero.

These are workflow observations, not a causal benchmark. There is no control
condition, randomized pairing, or performance claim in v1. A future A/B study
can reuse these exact task digests while keeping its condition and model
configuration outside the task bundles.

## Validation

From the repository root:

```sh
harbor check benchmarks/regression-v1/tasks/*
harbor run -c benchmarks/regression-v1/job-oracle.json
```

The Oracle job is the contract gate. Run it again after changing a task,
verifier, dependency, or image. `job-jacobian.json` is the observation config;
fill its deployment URL and token through the environment before running it.
The required environment variables are `JACOBIAN_IMAGE`, `JACOBIAN_MCP_TOKEN`,
`JACOBIAN_AUTH_TOKENS_JSON`, and `JACOBIAN_MODEL`. They are resolved from the
shell environment by `make agent-eval` — do not embed them in the job JSON
because Harbor's Docker compose mode does not resolve `${VAR}` templates in
job-level env blocks.

The 18 public research challenges under `benchmarks/research_challenges/` are
candidate material only. They are not silently promoted into this scored
dataset.
