---
name: harbor-benchmarks
description: Build, validate, and run Jacobian evaluations packaged as Harbor datasets. Use when authoring or changing Harbor tasks, independent verifiers, Oracle jobs, workflow fixtures, Jacobian observation jobs, task digests, or evaluation handoffs; keep generic Harbor CLI mechanics in the shared Harbor skills.
---

# Harbor Benchmarks

Use this skill as Jacobian's repository-specific layer for turning mathematical
cases into reproducible Harbor evaluations. It owns task contracts, verifier
integrity, dataset identity, Oracle validation, and Jacobian observation
configuration; it does not prescribe the mathematical strategy an evaluated
agent should use.

## Choose the evaluation boundary

Classify the work before editing a task:

- **Task/verifier validation:** parse the bundles, run the Oracle, and attack
  deliberate failure cases. This is harness evidence.
- **Jacobian workflow observation:** use a dataset with an observation profile,
  its rendered observation job, the authenticated MCP sidecar, and Harbor ATIF plus
  Jacobian telemetry. This is workflow evidence, not comparative performance.
- **Future causal comparison:** put control/treatment conditions in Harbor job
  configuration, outside task bundles, with identical task digests, prompts,
  models, budgets, environments, and seeds. Do not add an A/B condition merely
  to validate v1.

## Author or change a task

Read `AGENTS.md`, `CONTRIBUTING.md`, and
`docs/reference/capability-workflow-evaluations.md`. Canonical task bundles live
once under `benchmarks/tasks/<task-id>/`, using a globally unique, flat
directory name. Keep domain, field, provenance, and evaluation classification
in typed `task.toml` metadata rather than directory hierarchy. A dataset selects
canonical tasks through one `benchmarks/datasets/<dataset>/members/<task-id>.toml`
fragment per member; `suite.toml` contains only the dataset header and
`dataset.toml` is generated. Never copy a task into another dataset.

Before adding a task, run the benchmark planner and check for a global ID
collision. Manually authored or substantially transformed cases remain authored
tasks; create `benchmarks/adapters/<source>/` only when a pinned external source
can be converted reproducibly, with source revision and digest, license status,
included/excluded rows, deterministic conversion, pinned dependencies, Oracle
evidence, and parity evidence.

Every task has a maintainer `README.md`, frozen offline input, schema 1.4
metadata, concise provenance, an agent-visible
`environment/submission_schema.json`, hidden Oracle solution material, and a
separate clean-room verifier. Instructions must
be agent-agnostic: describe the mathematical outcome and evidence, never
capability IDs, tool sequences, preferred decompositions, or Jacobian details.

Verifiers must reject malformed submissions, symlink or workspace escapes,
wrong evidence paths or digests, incomplete scope, mismatched claims, and false
`VERIFIED` assertions. Score correctness, evidence validity, scope accuracy,
assurance calibration, and aggregate reward; force reward to zero for wrong
answers and false certification. Accept alternate mathematically valid
witnesses where the task permits them.

Keep Jacobian out of task bundles. Attach it only through the Harbor job's agent
configuration and MCP sidecar. Keep credentials, raw caches, host paths,
floating dependencies, and Oracle/verifier material out of agent-visible
files.

## Validate identity and behavior

Use the pinned Harbor runner from the repository:

```sh
uvx --from harbor==0.20.0 harbor --version
make benchmark-plan BASE=origin/main
make benchmark-sync
make benchmark-check
make benchmark-oracle DATASET=agent-workflow-v1 TASKS="task-id"
```

After any input, instruction, metadata, verifier, dependency, image, or task
contract change:

1. Recompute each canonical task content digest with Harbor's task model and
   regenerate every affected `dataset.toml`; do not invent a custom digest.
2. Parse/check every canonical task selected by member fragments and reject
   missing, duplicate, ambiguous, or escaping references.
3. Run every task through the dataset's Oracle job and require full applicable
   reward.
4. Exercise deliberate failures: empty or malformed output, wrong answers,
   forged or escaped evidence, incomplete scope, mismatched claims, timeouts,
   and false assurance.
5. Confirm alternate valid witnesses pass and scan task bundles for leakage,
   secrets, host paths, raw caches, and floating dependencies.

Do not treat `harbor sync` as a local digest calculator when the task is not
published. The committed dataset manifest and canonical task content must
agree. `benchmark-check` is outside the product `tests/` topology; keep Harbor
validation from entering product Python coverage.

The independent benchmark planner emits `run-benchmark-check`,
`run-benchmark-oracle`, `benchmark-oracle-scope`, an exact dataset/task/digest
matrix, and reasons. README-only task changes run contract checks without
Docker. Executable task changes run the exact task Oracle on pull requests.
Large multi-task edits are capped on the pull-request critical path and defer
their Oracle matrix to the merge queue.
Dataset membership and execution configuration changes defer their affected
dataset sweep to the merge queue; shared tooling, schemas, adapters, and unknown
integration changes escalate there to the full portfolio. Main pushes repeat
contract checks without replaying merge-queue Oracles. Scheduled, manual, and
`ci:benchmark-full` runs own explicit full-portfolio sweeps. The stable
`Benchmark Validation` workflow job is the only required branch-protection
context; dynamic Oracle jobs run at most four in parallel and upload result JSON,
verifier logs, source SHA, task digest, and Harbor version.

## Run Jacobian observation

Use the guarded entry point so the image reference is digest-pinned before
Harbor starts:

```sh
export JACOBIAN_IMAGE='registry.example/jacobian@sha256:<64-lowercase-hex-digits>'
export JACOBIAN_MCP_TOKEN='replace-with-at-least-32-character-token'
export JACOBIAN_AUTH_TOKENS_JSON='{"tokens":[{"tenant_id":"observation","token":"replace-with-at-least-32-character-token","scopes":["jacobian:use"]}]}'
export JACOBIAN_MODEL='your-model'
make agent-eval DATASET=agent-workflow-v1 EVAL_EXECUTE=1
```

Inspect Harbor ATIF together with Jacobian telemetry for capability discovery
and descriptions, invocation and parameter errors, artifact and verification
record flow, repeated or irrelevant calls, shell/file activity, tokens, time,
cost, and completion. Record the git tree, task digests, provider/runtime,
model/settings, prompt, seeds, raw traces, and structured reports.

## Handoff and publication

Report whether the result is task validation, a public regression, workflow
observation, or a causal comparison. Include exact commands, task digests,
Oracle/verifier identities, runtime state, raw artifact locations, validation
actually run, contamination limits, and open obligations.

Keep the dataset usable directly from the repository. Publishing to a Harbor
registry is optional and requires an explicit request; registry publication is
not part of task validation or local Jacobian observation.
