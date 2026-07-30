---
name: harbor-benchmarks
description: Build, validate, and run Jacobian evaluations packaged as Harbor datasets. Use when authoring or changing Harbor tasks, independent verifiers, Oracle jobs, regression-v1 fixtures, Jacobian observation jobs, task digests, or evaluation handoffs; keep generic Harbor CLI mechanics in the shared Harbor skills.
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
- **Jacobian workflow observation:** use the fixed tasks with
  `job-jacobian.json`, the authenticated MCP sidecar, and Harbor ATIF plus
  Jacobian telemetry. This is workflow evidence, not comparative performance.
- **Future causal comparison:** put control/treatment conditions in Harbor job
  configuration, outside task bundles, with identical task digests, prompts,
  models, budgets, environments, and seeds. Do not add an A/B condition merely
  to validate v1.

## Author or change a task

Read `AGENTS.md`, `CONTRIBUTING.md`, and
`docs/reference/capability-workflow-evaluations.md`. For the current suite,
work under `benchmarks/regression-v1/` and keep each task self-contained.

Every task should have frozen offline input, schema 1.4 metadata, concise
provenance, an agent-visible `environment/submission_schema.json`, hidden
Oracle solution material, and a separate clean-room verifier. Instructions must
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
make test-plan BASE=origin/main
make check
```

After any input, instruction, metadata, verifier, dependency, image, or task
contract change:

1. Recompute each task content digest with Harbor's task model and update the
   corresponding `dataset.toml` entry; do not invent a custom digest.
2. Parse/check the task bundles with Harbor.
3. Run every task through `job-oracle.json` and require full applicable reward.
4. Exercise deliberate failures: empty or malformed output, wrong answers,
   forged or escaped evidence, incomplete scope, mismatched claims, timeouts,
   and false assurance.
5. Confirm alternate valid witnesses pass and scan task bundles for leakage,
   secrets, host paths, raw caches, and floating dependencies.

Do not treat `harbor sync` as a local digest calculator when the task is not
published. The committed dataset manifest and local task content must agree.

## Run Jacobian observation

Use the guarded entry point so the image reference is digest-pinned before
Harbor starts:

```sh
export JACOBIAN_IMAGE='registry.example/jacobian@sha256:<64-lowercase-hex-digits>'
export JACOBIAN_MCP_TOKEN='replace-with-at-least-32-character-token'
export JACOBIAN_AUTH_TOKENS_JSON='{"tokens":[{"tenant_id":"observation","token":"replace-with-at-least-32-character-token","scopes":["jacobian:use"]}]}'
export JACOBIAN_MODEL='your-model'
make agent-eval
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
