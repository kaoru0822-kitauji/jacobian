# Symbolic coordination repeated comparison

[Documentation home](../../index.md) · [Evaluation methods](evaluation-methods.md) ·
[Trajectory telemetry](symbolic-coordination-trajectory-telemetry.md)

The repeated comparison contract composes the existing host-local Codex runner
and trajectory normalizer. It does not change `symbolic-coordination-v1` task
instructions, prompts, verifiers, Jacobian capabilities, policy, or reasoning
semantics. Its evidence class is `host-local-workflow-observation`, and its
reports always set `causal_claim_authorized` to `false`.

The pilot matrix has two tasks from different families, two repetitions, and
three conditions, for exactly 12 planned model executions:

- A: no Jacobian and no audit;
- B: Jacobian and no audit; and
- C: Jacobian followed by the fixed targeted contract audit and at most one
  coherent revision.

The selected tasks are `symbolic-coordination-near-miss-01` and
`symbolic-coordination-grid-exhausted-01`. The runner uses the PR2/PR3 model
contract (`gpt-5.3-codex-spark`, medium reasoning) and file-backed ChatGPT
login. It rejects API-key auth or model substitution.

## Frozen manifest

Planning performs the full Codex auth/model/isolation preflight and writes an
immutable `experiment-manifest.json`. The manifest binds:

- the clean source revision and branch plus operator-supplied stack SHAs;
- task IDs, families, Harbor digests, public-file hashes, and verifier hashes;
- the exact condition contracts, repetition count, and counterbalanced order;
- model contract, reasoning effort, Codex version and executable, ChatGPT auth
  mode, prompt digests, token/time/tool-call/cost budget availability;
- MCP executable and policy configuration; and
- Python, platform, Harbor, lockfile, pilot-manifest, preflight, and sampling
  availability metadata.

The manifest ID is the SHA-256 digest of its canonical body. Loading fails on
manifest or preflight drift. Every run has a unique deterministic ID and its
own fresh run root. The order uses versioned permutations across
task/repetition blocks, so runs do not always execute A, then B, then C.

## Resumption and failure handling

Before any new model execution, the runner requires the same clean source,
task contracts, model, reasoning effort, and prompts. Existing run roots are
accepted only after PR3 independently replays their complete artifact index,
snapshot, raw JSONL, stage telemetry, submissions, verifier results, reasoning
logs, and task bindings. A valid completed wrong answer is an observation and
is never retried. Corrupt, partial, duplicated, substituted, or drifted
artifacts stop the run.

The default runner does not retry. A failure before creation of a run root is
recorded as `PRE_MODEL_FAILURE` and the command stops; it is not converted into
a mathematical result. Incomplete model/runtime executions remain separately
classified as infrastructure failures. An explicit `SC_COMPARISON_RETRY_INFRA=1`
permits only these two classes to be retried and first moves their immutable
artifacts into `retry-history`; it cannot retry a completed mathematical
failure. The 12-run pilot does not use this option. Operators must not rerun
the pilot based on its mathematical outcomes. Analyzer or renderer fixes reuse
the preserved raw roots.

## Report contract

The normative schemas are
[`symbolic-coordination-experiment-v1.schema.json`](../../../benchmarks/schemas/symbolic-coordination-experiment-v1.schema.json)
and
[`symbolic-coordination-comparison-v1.schema.json`](../../../benchmarks/schemas/symbolic-coordination-comparison-v1.schema.json).
The typed implementation is
`benchmarks.tooling.symbolic_coordination_comparison`.

JSON and Markdown reports retain per-run:

- acquisition and infrastructure status, separately from mathematical failure;
- clean-room correctness, evidence validity, scope, assurance, input/artifact
  bindings, false certification, reward, and acceptance;
- audit repair/regression class and revision state;
- exact tokens and wall time when exposed, tool/capability counts, reasoning
  compliance, protocol violations, and source artifact-index digest.

Condition summaries report explicit numerators and denominators with 95%
Wilson intervals. Tokens and wall time are totaled only if every included
observed run has exact telemetry; otherwise the total remains unavailable with
an exact-run count. ChatGPT login does not expose monetary cost, so cost and
cost-per-accepted remain unavailable rather than estimated.

The paired A→B and B→C tables are matched by task and repetition. They report
both-failed, left-only, right-only, both-accepted, discordant and missing pairs,
the paired acceptance difference, and the two-sided exact paired-binomial test
(the exact McNemar test for binary discordance). Per-task reliability retains
condition-specific denominators. Partial collections remain reportable without
imputing missing or infrastructure-failed outcomes.

These statistics describe a tiny nondeterministic pilot. They do not establish
causal lift, general model quality, or product capability value.

## Commands

First commit the implementation so the clean source SHA is stable. Then plan
outside the repository, supplying the exact stack SHAs:

```sh
make symbolic-coordination-comparison-plan \
  SC_COMPARISON_ROOT=/tmp/symbolic-comparison-pilot \
  SC_COMPARISON_STACK_REVISIONS="origin_main=<sha> pr2=<sha> pr3=<sha> pr4=<sha>"
```

Review the 12 manifest entries, then execute exactly once:

```sh
make symbolic-coordination-comparison-run EVAL_EXECUTE=1 \
  SC_COMPARISON_ROOT=/tmp/symbolic-comparison-pilot \
  SC_COMPARISON_MAX_EXECUTIONS=12
```

Resume with the same command after an operator-confirmed interruption; valid
completed roots are verified and skipped. Finally emit outputs outside the
experiment root:

```sh
make symbolic-coordination-comparison-report \
  SC_COMPARISON_ROOT=/tmp/symbolic-comparison-pilot \
  SC_COMPARISON_OUTPUT=/tmp/symbolic-comparison.json \
  SC_COMPARISON_MARKDOWN=/tmp/symbolic-comparison.md
```

The report command refuses to overwrite outputs.

## Known limits

Codex does not expose a sampling seed, temperature, reasoning-log token cost,
or ChatGPT monetary cost. Tool-call count is observed but not capped by the
underlying PR2 harness. The pilot has only four task/repetition pairs per
contrast, so intervals are wide and exact tests have very low resolution.
