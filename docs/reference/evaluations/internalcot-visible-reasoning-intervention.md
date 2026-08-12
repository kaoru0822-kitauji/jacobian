# Internalcot visible-reasoning intervention

Status: **frozen before accepted model runs; research-only**.

This bounded operator study asks whether the active
[`internalcot`](https://github.com/morluto/internalcot) prompt, skill, and CLI
intervention changes observable Jacobian use, and whether its model-authored
visible notes carry held-out diagnostic information beyond task/output structure
and passive `math.find`/`math.run` telemetry. It follows the passive trajectory
work in draft PR #1259, but estimates a different quantity: `b*` is produced by
an intervention, not observed passively.

The contract is
[`benchmarks/config/internalcot-trajectory-intervention-v1.json`](../../../benchmarks/config/internalcot-trajectory-intervention-v1.json).
It freezes eight tasks in four complete-family holdouts, two repetitions, two
arms, all 16 paired arm orders, authenticated `gpt-5.4-mini` at medium effort,
the common prompt, package and skill hashes, diagnostics, behavior metrics,
bootstrap, coverage gates, and stopping rules. The 32 fresh trials compare:

- control: `(x, y, tau_tools)` and `(x, y, b, tau_tools)`;
- treatment: `(x, y, tau_tools)` and `(x, y, b*, tau_tools)`.

The predictive contrast and paired behavioral contrast are reported separately.
A conditional `b*` gain is an association inside the treatment arm. A paired
treatment-minus-control effect concerns the bundled active intervention. Neither
licenses a claim about hidden reasoning or information available to a passive
observer.

## Current product boundary

The study is bound to main at `f37a5b205ccdb3537db47e7e055e06ee514d6e62`,
after PRs #1256 and #1265. Each trial uses a fresh current
`jacobian-remote-mcp` loopback server and only the two default operations,
`math.find` and `math.run`. Current top-level `verification_record_uri` presence
is evidence presence, never inferred assurance. Producer and checker operations
remain separate catalog IDs.

This branch adds benchmark configuration, operator tooling, tests, aggregate
evidence, and this reference only. It does not add a production reasoning
protocol, observer, retention path, workflow abstraction, MCP tool, generic
result field, or checker authority. The final engineering decision is therefore
research-only even if every statistical gate passes. A passive product proposal
would require an independent passive replication and separate architecture
review.

## Execution and privacy

Prepare an isolated prefix containing exactly `internalcot@0.2.3`. The runner
verifies the package-lock integrity, the packaged official discovery skill, and
the exact output of `internalcot skill` against their frozen SHA-256 bindings
before execution. Then run the substantive
collection and analysis in named `tmux` sessions:

```bash
python -m benchmarks.tooling.active_reasoning_intervention run \
  --execute \
  --internalcot-prefix /tmp/jacobian-internalcot-runtime-v1 \
  --output /tmp/jacobian-internalcot-results-v1

python -m benchmarks.tooling.active_reasoning_intervention analyze \
  --results /tmp/jacobian-internalcot-results-v1 \
  --output /tmp/internalcot-visible-reasoning-report.json
```

Raw workspaces, JSONL, server logs, prompts, submissions, agent messages,
`internalcot` notes, tool arguments/results, verifier internals, and hidden
reasoning stay host-local and are not committed. The projector retains only
bounded structural features, counts, labels, behavior metrics, adherence facts,
aggregate predictions/effects, and cryptographic bindings. Treatment adherence
is fail-closed: the pinned workflow must load, at least two note calls must
succeed, the first note must precede substantive operations, and the final note
must follow them and precede the final answer. Any control note call is treated
as contamination.

The tasks were used in prior passive work. Pairing and complete-family holdout
control known task identity within this intervention, but do not turn the study
into an unseen-task capability evaluation.
