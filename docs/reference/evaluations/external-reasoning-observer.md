# External reasoning observer

[Evaluation references](index.md) · [Capability surface](../tools.md)

The external reasoning observer is a post-run evaluation adapter. It derives a
bounded audit record from two already-completed artifacts:

- a Codex JSONL or Harbor ATIF agent trajectory; and
- the Jacobian MCP runtime log.

It is not an MCP tool, runtime mode, prompt, persistence service, or source of
mathematical evidence. It runs only after the agent and verifier have exited.
Consequently it cannot gate `math.find`, add fields to `math.run`, require a
phase sequence, authorize a checker, or change assurance.

The typed contract is
`benchmarks.tooling.external_reasoning_observer.ExternalReasoningObservation`.
Its `causal_claim_authorized` and `affects_mathematical_assurance` fields are
always `false`.

## Recorded evidence

The runtime log is authoritative for automatic events. The observer preserves
the server-emitted tool name, status, request and trace digests, trace source,
duration, response size, argument digest, and capability-attempt fields. It
normalizes only terminal line wrapping inside SHA-256 digests. It does not
reconstruct tool calls from prose or copy tool arguments or results from the
agent trace.

Each server event receives an operator-supplied trial ID and a sequence within
the runtime log. A non-`none` server request digest is the only cross-event
correlation key. The observer does not ask the model to mint run or call IDs,
and it does not infer chronology between the independently ordered agent and
server artifacts. Both sources must resolve beneath the operator-bound trial
root without crossing a symlink; a source from another trial is rejected.

Agent summaries are optional self-reports. Only explicit, user-visible agent
messages are eligible:

- Codex `item.completed` events whose item type is `agent_message`; or
- non-copied ATIF steps whose source is `agent` and whose `message` is text.

The observer excludes prompts, ATIF `reasoning_content`, hidden
chain-of-thought, tool arguments, and tool results. A valid trace with no agent
messages is a complete observation with zero summaries.

## Privacy, retention, and bounds

Each retained message is redacted for bearer tokens, OpenAI-style API keys,
user home-directory prefixes, and common temporary-workspace paths, then
bounded to 512 UTF-8 bytes. The record
states the original post-redaction byte count, whether truncation occurred,
and the redaction count. Source bindings retain only a basename, byte count,
and SHA-256 digest; they do not copy source paths.

The derived JSON is an operator-controlled evaluation artifact. Do not publish
raw traces or derived summaries without the evaluation's retention and review
policy. The observer contract is not consent to retain model or user content.

## Failure semantics

Missing, unreadable, or malformed sources produce an `INCOMPLETE` observation
and bounded diagnostic codes. Valid events parsed before or after a malformed
entry remain visible. Observer failure never changes the completed agent,
verifier, mathematical result, artifact, or assurance level.

The server event coverage metric is the fraction of log entries carrying a
Jacobian event marker that parsed into typed records. Zero explicit summaries
does not reduce server coverage and is not an error.

## Usage

Run the observer over immutable copies of one trial's artifacts:

```sh
uv run python -m benchmarks.tooling.external_reasoning_observer \
  --trial-id graph-counterexample-r01 \
  --trial-root results/attempt-0 \
  --agent-trace results/attempt-0/artifacts/logs/agent/trajectory.json \
  --server-log results/attempt-0/artifacts/logs/jacobian/mcp.log \
  --output results/attempt-0/external-reasoning-observation.json
```

The command exits zero only for a `COMPLETE` record. It still writes a partial
record before returning nonzero for an `INCOMPLETE` observation.

The frozen exploratory study contract is
[`external-reasoning-observer-v1.json`](../../../benchmarks/config/external-reasoning-observer-v1.json).
Its baseline and treatment use the same completed trajectory: treatment is the
post-run derivation only. Agent behavior, tool calls, tokens, verifier results,
and false-certification classification are therefore paired invariants rather
than outcomes the observer is allowed to influence.

See the [completed pilot report](external-reasoning-observer-pilot.md) for the
authenticated weak-model observations, evidence digests, limitations, and keep
decision.
