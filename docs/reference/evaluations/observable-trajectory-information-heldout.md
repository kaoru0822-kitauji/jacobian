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

Run from a clean tracked checkout with the pinned development environment and
an authenticated Codex CLI. All model execution is explicit:

```bash
python -m benchmarks.tooling.trajectory_information run \
  --config benchmarks/config/trajectory-information-v2.json \
  --output /tmp/jacobian-trajectory-information-v2 \
  --execute

python -m benchmarks.tooling.trajectory_information analyze \
  --config benchmarks/config/trajectory-information-v2.json \
  --results /tmp/jacobian-trajectory-information-v2 \
  --output /tmp/jacobian-trajectory-information-report-v2.json
```

The engineering gate remains fail-closed. A retention change is allowed only
when the complete event-coverage gate and the frozen held-out uncertainty
thresholds pass. Otherwise the outcome remains research-only.
