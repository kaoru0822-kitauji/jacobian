# Agent workflow observations

[Documentation home](../index.md)

Jacobian’s current mathematical observation suite is the committed Harbor
[`regression-v1`](../../benchmarks/regression-v1/README.md) dataset. It contains
fourteen self-contained tasks covering graph counterexamples, graph artifact
composition, exact finite partitions, SAT witnesses, rational linear systems,
Hermite normal form, polynomial normalization, polynomial-map collisions,
matrix and subspace counterexamples, polynomial-tail reasoning, and exact
logarithmic algebra, and proof-audit workloads.

The task bundles are agent-agnostic. A prompt says only that a mathematical
toolbox may be available; it does not prescribe capability IDs, decomposition,
verification order, or stopping criteria. Each task freezes its offline input,
schema 1.4 metadata, Oracle-only solution, and separate clean-room verifier.

## Validation boundary

Task and verifier validation is separate from model observation. First parse and
check the task bundles with Harbor, then run the Oracle job:

```sh
harbor check benchmarks/regression-v1/tasks
harbor run -c benchmarks/regression-v1/job-oracle.json
```

The verifier emits `correctness`, `evidence_validity`, `scope_accuracy`,
`assurance_calibration`, and aggregate `reward`. Wrong answers, incomplete
finite scope, malformed or escaped evidence, mismatched claims, timeouts, and
unsupported `VERIFIED` claims remain non-conclusions. Oracle validation must be
rerun after task contracts, verifiers, dependencies, generated images, or
image digests change.

## Jacobian-enabled observation

The observation job runs the same fixed task digests with one agent configuration
and an authenticated per-trial Jacobian MCP service. The service is started
under `COMPUTE_VERIFY_NO_RETRIEVAL`; the bearer token is injected by the Caddy
sidecar and is not part of the task prompt.

```sh
export JACOBIAN_IMAGE='registry.example/jacobian@sha256:...'
export JACOBIAN_MCP_TOKEN='replace-with-at-least-32-character-token'
export JACOBIAN_AUTH_TOKENS_JSON='{"tokens":[{"tenant_id":"observation","token":"replace-with-at-least-32-character-token","scopes":["jacobian:use"]}]}'
export JACOBIAN_MODEL='your-model'
make agent-eval EVAL_EXECUTE=1
```

Inspect Harbor ATIF together with Jacobian telemetry for discovery and
description use, invocation and parameter errors, artifact and
verification-record flow, repeated or irrelevant calls, shell/file activity,
tokens, time, cost, and completion. This is workflow observation only; v1 has
no control condition, randomized pairing, experiment orchestrator, or causal
performance claim.

## Research challenges and future A/B

The 18 public research challenges under `benchmarks/research/challenges/` remain
candidate material. They are answer-visible and are not held-out performance
evidence.

Add a control condition only when the question becomes whether Jacobian causes
an improvement relative to no Jacobian. That experiment belongs in the Harbor
job configuration, not in task bundles, and must reuse the exact task digests,
agents, models, prompts, budgets, environments, and seeds. Held-out
performance claims require a separately frozen task set and report every run;
workflow observations must not be presented as comparative evidence.
