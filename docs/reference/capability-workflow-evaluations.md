+# Capability workflow evaluations

[Documentation home](../index.md)

This document defines the boundary between Jacobian capability development and
agent-evaluation evidence. The current Harbor surface is the committed
[`regression-v1`](../../benchmarks/regression-v1/README.md) dataset: twenty-four
self-contained tasks for graph counterexamples, graph artifact composition,
finite coverage, SAT witnesses, exact rational systems, Hermite normal form,
polynomial normalization, polynomial-map collisions, matrix and subspace
counterexamples, polynomial-tail reasoning, exact logarithmic algebra, modular
obstruction certificates, divisibility-witness construction, layered
proof/evaluator meta-verification, finite
claim auditing, exact probabilistic auditing, autoformalization semantic
alignment, grounded premise retrieval with proof-DAG reconstruction, symbolic
Euclidean geometry, constructive real analysis, compiler-feedback proof repair,
finite combinatorial construction, and optimization-proof repair.

## Task and verifier validation

Every task is agent-agnostic and contains frozen offline input, schema 1.4
metadata, an Oracle-only solution, and a separate clean-room verifier. The
prompt may mention that a mathematical toolbox is available, but it does not
name capability IDs or prescribe decomposition, invocation order,
verification order, or stopping criteria.

Validate the bundles and then run the Oracle:

```sh
harbor sync benchmarks/regression-v1/dataset.toml
harbor check benchmarks/regression-v1/tasks
harbor run -c benchmarks/regression-v1/job-oracle.json
```

The verifier scores correctness, evidence validity, scope accuracy, assurance
calibration, and aggregate reward. Wrong answers, incomplete scope, malformed
or escaped evidence, mismatched claims, timeouts, and unsupported `VERIFIED`
claims are non-conclusions. Rerun Oracle after any task-contract, verifier,
dependency, generated-image, or image-digest change.

## Jacobian-enabled workflow observation

The observation job uses the same fixed task contents with one agent
configuration and an authenticated per-trial Jacobian MCP service. The service
runs under `COMPUTE_VERIFY_NO_RETRIEVAL`; the Caddy sidecar injects the bearer
token, keeping credentials out of task prompts.

```sh
export JACOBIAN_IMAGE='registry.example/jacobian@sha256:...'
export JACOBIAN_MCP_TOKEN='replace-with-at-least-32-character-token'
export JACOBIAN_AUTH_TOKENS_JSON='{"tokens":[{"tenant_id":"observation","token":"replace-with-at-least-32-character-token","scopes":["jacobian:use"]}]}'
export JACOBIAN_MODEL='your-model'
make agent-eval EVAL_EXECUTE=1
```

Analyze Harbor ATIF alongside Jacobian telemetry for capability discovery and
descriptions, invocation and parameter errors, artifact and verification
record flow, repeated or irrelevant calls, shell/file activity, tokens, time,
cost, and completion. This is workflow observation only. Version 1 has no
control condition, randomized pairing, experiment orchestrator, or causal
performance claim.

## Candidate material and future experiments

The 18 public research challenges under
`benchmarks/research/challenges/` remain candidate material. They are useful
for discovery and workflow reproduction, but are not hidden answers or
held-out performance evidence. Lean and external proof backends remain outside
this Harbor dataset until their pinned task-container runtimes are reliable.

Add a control condition only when the question becomes whether Jacobian causes
an improvement relative to no Jacobian. Keep that comparison in Harbor job
configuration, outside task bundles, and reuse exact task digests, agents,
models, prompts, budgets, environments, and seeds. Held-out performance
claims require a separately frozen task set and an explicit report of every
run.
