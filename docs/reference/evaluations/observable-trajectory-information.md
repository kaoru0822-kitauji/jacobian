# Observable trajectory information

[Documentation home](../../index.md) · [Evaluation references](index.md)

This bounded research harness asks whether server-observable Jacobian events add
useful trajectory information beyond a task, final answer, and bounded visible
messages. It is an operator-run evaluation tool, not a runtime observer, a
workflow engine, or a source of verification authority.

## Observation contract

The preregistered contract is `benchmarks/config/trajectory-information-v1.json`:

- `x` is the Harbor task identity and agent-visible task contract;
- `y` is the final submission structure plus the exact task-verifier outcome;
- `b` contains only non-final, user-visible agent messages, redacted and bounded
  to 512 UTF-8 bytes per message, 32 messages, and 8,192 bytes per trial; and
- `τ_tools` is the ordered sequence of Jacobian server events for `math.find`
  and `math.run`, restricted to typed metadata such as operation ID, execution
  status, result type, assurance, checker flag, artifact counts, and safe
  digests.

Neither projection contains hidden reasoning, tool arguments, tool results,
submission contents, or verifier internals. Raw Codex transcripts, fresh trial
workspaces, and MCP logs remain host-local. The checked-in evidence is an
aggregate report with digests and structural counts only.

The five diagnostics are next tool-action class, checker rejection/recovery,
milestone attainment, terminal exact-verifier success, and tool-use failure
class. Execution status, mathematical correctness, and checker-backed assurance
remain separate. In particular, a Harbor reward never becomes Jacobian
`VERIFIED` evidence.

## Run and analyze

Use a clean, tracked checkout with the pinned development dependencies and an
authenticated Codex installation. Model execution is deliberately guarded:

```bash
python -m benchmarks.tooling.trajectory_information run \
  --config benchmarks/config/trajectory-information-v1.json \
  --output /tmp/jacobian-trajectory-information-v1 \
  --execute

python -m benchmarks.tooling.trajectory_information analyze \
  --config benchmarks/config/trajectory-information-v1.json \
  --results /tmp/jacobian-trajectory-information-v1 \
  --output /tmp/jacobian-trajectory-information-report-v1.json
```

The runner validates every pinned Harbor task digest, starts a fresh anonymous
loopback MCP server for each trial, runs the exact clean-child task verifier,
and binds every retained record to its source and raw-artifact SHA-256 digests.
The analyzer rejects missing or changed records, raw artifacts, malformed server
events, and incomplete marker coverage before reporting any result.

The frozen plan allowed a simplest-defensible fallback after two failed
methods. That fallback uses exact-signature contingency purity over fixed
presence bins. It is transductive and descriptive: it cannot satisfy held-out
decision thresholds or authorize a production observer change.

## Pilot result

The first pilot completed 12 authenticated single-trial tasks: three exact
passes, three partial rewards, and six zero rewards. Eight trajectories
contained server tool events. The descriptive mean macro-F1 increment was
`+0.1671` for `τ_tools` over `x+y` and `+0.0291` for `b` over
`x+y+τ_tools`; the latter was concentrated in milestone and next-action
classification.

These values are not held-out estimates. The corpus had only one checker use,
no checker rejection/recovery variation, and no server tool error. The result
is therefore `INCONCLUSIVE_RESEARCH_ONLY`: neither minimizing the observer to
`τ_tools` nor preserving `b` in production is supported. See the immutable
aggregate [pilot report](../../../benchmarks/evidence/observable-trajectory-information-v1/report.json).
