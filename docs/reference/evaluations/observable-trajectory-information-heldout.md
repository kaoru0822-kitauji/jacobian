# Held-out observable trajectory replication

[Documentation home](../../index.md) · [Evaluation references](index.md)

This replication tests whether bounded visible-summary structure `b` adds
stable trajectory-diagnostic information after task/output structure and
server-observed `math.find` / `math.run` telemetry are known. It does not reuse
the transductive scores from the first pilot as evidence.

## Frozen boundary

The preregistration is
`benchmarks/config/trajectory-information-v2.json`. It fixes twelve tasks that
were absent from v1, arranged as four complete three-task families:

- matrix certificates;
- polynomial and field reasoning;
- finite discrete mathematics; and
- proof repair and manual analysis.

Every model fold holds out one complete family, including all task repetitions
and all next-action prefix rows. Feature definitions and engineering thresholds
come from the pre-label v1 design; no v2 label may select a feature, family,
threshold, or stopping rule. The fixed model is three-nearest-neighbor with
train-fold-only scaling. Uncertainty uses task-block bootstrap resampling of
already-held-out predictions.

The four conditions are `x+y`, `x+y+b`, `x+y+tau_tools`, and
`x+y+b+tau_tools`. Diagnostics cover the next action, checker state, recovery,
mathematical milestone, and exact terminal verifier success. The telemetry
ablation separately tests call structure, public capability identity, outcome,
cost, and digest-binding fields.

## Privacy and integrity

Each authenticated Codex trial receives a fresh public task workspace and a
fresh anonymous loopback Jacobian state directory. The runner binds the clean
source revision, frozen task digests, config and collector bytes, model/runtime
settings, raw transcript, server log, trial record, and exact clean-child
verifier result.

Raw prompts, agent-message text, tool arguments, tool results, submissions,
evidence, verifier internals, and hidden reasoning remain host-local. The
committed report may contain only aggregate metrics, public task identities,
structural counts, labels, limitations, and SHA-256 bindings. A task verifier
outcome never changes Jacobian checker authorization or assurance semantics.

## Reproduce

Run from a clean tracked checkout with an authenticated Codex CLI. The command
below pins Harbor 0.20.0 while installing the selected checkout and the small
Harbor runtime extras into an isolated `uvx` environment. All model execution
is explicit:

```bash
uvx --from harbor==0.20.0 --with-editable . \
  --with tomli-w==1.2.0 --with jsonschema \
  python -m benchmarks.tooling.trajectory_information run \
  --config benchmarks/config/trajectory-information-v2.json \
  --output /tmp/jacobian-trajectory-information-v2 \
  --execute

uvx --from harbor==0.20.0 --with-editable . \
  --with tomli-w==1.2.0 --with jsonschema \
  python -m benchmarks.tooling.trajectory_information analyze \
  --config benchmarks/config/trajectory-information-v2.json \
  --results /tmp/jacobian-trajectory-information-v2 \
  --output /tmp/jacobian-trajectory-information-report-v2.json
```

The engineering gate remains fail-closed. A retention change is allowed only
when the complete event-coverage gate and the frozen held-out uncertainty
thresholds pass. Otherwise the outcome remains research-only.

## Held-out result

The fixed run completed all 24 trials (twelve tasks, two repetitions, four
families) with `codex-cli 0.147.0`, `gpt-5.4-mini`, and medium reasoning. Every
command exited. Complete-family holdout therefore remains inductive at the
family level; the task-identity resubstitution score is reported only as a
non-generalizing reference.

Held-out macro-F1 was:

| Diagnostic | x+y | +b | +tau | +b+tau |
| --- | ---: | ---: | ---: | ---: |
| Next tool action | 0.271 | 0.326 | 0.401 | 0.382 |
| Checker state | 0.295 | 0.295 | 0.584 | 0.477 |
| Recovery state | 0.429 | 0.442 | 0.442 | 0.429 |
| Mathematical milestone | 0.621 | 0.631 | 0.496 | 0.408 |
| Terminal verifier success | 0.778 | 0.705 | 0.747 | 0.621 |

Across the five eligible diagnostics, telemetry added `0.0553` mean macro-F1
over x+y. Conditional on x+y+tau, visible summaries changed mean macro-F1 by
`-0.0706`; the task-block bootstrap 95% interval was `[-0.1185, -0.0060]`.
Every per-diagnostic conditional b increment was negative. This is predictive
association in a small weak-model sample, not a causal result.

Outcome telemetry was the strongest field group by both mean add-only gain
(`0.0459`) and mean drop-one loss (`0.0441`), followed by call structure
(`0.0340`, `0.0383`). Binding and cost fields had smaller add-only gains;
capability identity had no positive mean gain (`-0.0013`). Current MCP logs
expose verification-record URI presence rather than assurance. The analyzer
retains that as evidence presence and does not infer an assurance level.

The event-rich corpus contained 23 server-tool trajectories, four successful
producer/checker chains, one checker-rejection trajectory, four recovered
trajectories, four tool-failure trajectories, two discovery-only trajectories,
and one no-tool trajectory. The preregistered minima required two checker
rejections and two no-tool trajectories. Those two coverage checks failed, so
the decision is `INCONCLUSIVE_RESEARCH_ONLY` even though the metric thresholds
otherwise point toward data minimization. No retention or product behavior was
changed.

The committed aggregate [held-out report](../../../benchmarks/evidence/observable-trajectory-information-v2/report.json)
binds the frozen config, raw host-local manifest, collection source and bytes,
post-collection analyzer bytes, projections, uncertainty, baselines, and field
ablations. It contains no raw prompts, agent messages, hidden reasoning, tool
arguments/results, submissions, or verifier internals.
