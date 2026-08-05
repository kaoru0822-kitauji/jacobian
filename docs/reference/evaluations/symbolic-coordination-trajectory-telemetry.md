# Symbolic coordination trajectory telemetry

[Documentation home](../../index.md) · [Evaluation methods](evaluation-methods.md) ·
[Benchmark contracts](benchmark-contracts.md)

The host-local `symbolic-coordination-v1` runner emits deterministic trajectory
telemetry schema version 1. The record is a descriptive
`host-local-workflow-observation`; `causal_claim_authorized` is always `false`.
It does not score prose, infer intent, use a learned judge, or change the task
verifier.

The normative JSON Schema is
[`benchmarks/schemas/symbolic-coordination-trajectory-v1.schema.json`](../../../benchmarks/schemas/symbolic-coordination-trajectory-v1.schema.json).
The authoritative typed model and loader live in
`benchmarks.tooling.symbolic_coordination_trajectory`.

## Source and integrity contract

The operator command accepts one or more complete PR3 run roots. Before it
emits any record, it requires all of the following:

- the content-addressed `artifact-index.json` is schema-valid, sorted, unique,
  escape-free, and exactly covers every other regular file in the run;
- every indexed byte count and SHA-256 digest matches;
- the runtime snapshot ID equals the canonical digest of the snapshot body,
  prompt files match their frozen digests, and condition/model/task bindings
  agree;
- every non-empty Codex JSONL line is a JSON object, and the committed stage
  telemetry agrees with a fresh parse of that JSONL;
- public task files match the snapshot hashes;
- reasoning-log index paths, counts, and digests agree with their JSONL exports;
- initial/final submission state, revision flag, initial/final verifier result,
  condition result, and top-level run result agree.

Missing or inconsistent source data is an error. A declared incomplete model
run is still analyzable: missing token usage or verifier output remains
`UNAVAILABLE`/`INCOMPLETE` when the condition's infrastructure failure list
declares it. The loader never converts missing data into zero or a conclusion.

## Deterministic classifications

Rules are closed and versioned with schema v1:

- **Discovery:** an MCP call named `capability.describe`.
- **Invocation:** an MCP call named `capability.invoke`.
- **Schema-valid call:** invocation arguments are an object with string
  `capability_id` and object `payload`, and no typed invalid-parameter error
  code is present.
- **Executable call:** a schema-valid response exposes typed
  `execution.status`.
- **Failed call:** the MCP item failed, returned `isError`, or has execution
  status `ERROR`, `TIMEOUT`, or `CANCELLED`.
- **Repeated call:** the same tool and canonical SHA-256 argument digest occurs
  more than once. Each occurrence after the first is marked as repeated.
- **Task relevance:** each symbolic-coordination family owns the applicable
  domain set. Version 1 admits the `polynomial` capability domain for all six
  pilot families; a capability invocation from another domain is irrelevant.
  Discovery, reasoning, resource, and shell calls are not classified as
  irrelevant capability invocations. This deliberately coarse rule preserves
  alternate polynomial strategies.
- **Candidate/checker flow:** successful typed outputs from
  `polynomial.map.inverse.candidate_synthesize`,
  `polynomial.map.collision_witness`,
  `polynomial.map.collision.search`, and
  `polynomial.map.compute_jacobian` count only when their respective candidate,
  witness, or Jacobian field is non-null. Their applicable later checkers are,
  respectively, `polynomial.map.inverse.verify`,
  `polynomial.map.collision.verify`, and
  `polynomial.map.keller_condition.verify`. A later non-failed applicable
  checker is required.
- **Recovery:** a failed or non-conclusive invocation is recovered only by a
  later completed, non-failed invocation of the same capability. Audit repair
  is separately established by clean-room verifier results.
- **Search outcomes:** typed `TIMEOUT`, `CANCELLED`, `INCOMPLETE`, `UNKNOWN`,
  and non-complete completeness states remain non-conclusions. Exact
  `GRID_EXHAUSTED` is reported separately as bounded exhaustion. An unresolved
  non-conclusion followed by a final `TRUE` or `FALSE` submission is an
  improper escalation.
- **Artifacts:** creation comes from typed `artifact_uris`; handoff/reuse
  requires the exact URI in a later invocation argument. Stale/misbound and
  substituted artifacts use closed diagnostic-code sets, not message text.
  Final input/artifact binding remains the clean-room verifier's score.
- **Reasoning protocol:** condition A is `NOT_APPLICABLE`. Required modes are
  complete only when the existing parser establishes the exact
  `PLAN`/`BEFORE_TOOL`/`AFTER_TOOL`/`FINAL` protocol and durable exported entry
  counts agree. Bytes are exact file sizes. Reasoning-log token overhead is
  `UNAVAILABLE` because Codex does not expose stage-separated log tokens; it is
  never estimated from characters or bytes.
- **Audit:** clean-room verifier reward transitions define `REPAIR` (rejected
  to accepted with a revision), `REGRESSION` (accepted to rejected with a
  revision), `ALREADY_CORRECT`, `UNCHANGED_FAILURE`, or `INCOMPLETE`. Audit
  prose and self-reported checks have no scoring authority. Conditions A/B are
  `NOT_APPLICABLE` because they have no post-solution audit.

Protocol violations are emitted as stable codes for invalid calls, missing
applicable checkers, irrelevant calls, unresolved timeout/incomplete
overclaims, stale/substituted artifacts, incomplete required reasoning logs,
and incomplete infrastructure.

## Fields and aggregates

Each condition record keeps these dimensions separate:

- infrastructure completion and failures;
- clean-room correctness, evidence validity, scope accuracy, assurance
  calibration, input/artifact binding, false certification, and reward;
- exact primary/audit token fields when Codex exposes them;
- primary/audit wall time;
- discovery, invocation, schema-valid, executable, failed, repeated,
  irrelevant, producer, checker, recovery, MCP, and shell counts;
- search outcomes, artifact flow, reasoning protocol, submissions, and audit
  transition.

The bundle contains per-task A/B/C rows and overall A/B/C plus `ALL` rows.
Verifier dimensions are averaged independently. Call, search, artifact,
reasoning-log, protocol, and audit dimensions are separately summed rather
than collapsed into correctness. Aggregate tokens include every applicable
stage (primary plus condition C audit) and are present only when every included
run has exact usage; otherwise the total is `null` with an exact-run count.
Wall time follows the same fail-closed availability rule.

## Operator command

Write outputs outside the immutable run roots:

```sh
make symbolic-coordination-trajectory-telemetry \
  SC_TRAJECTORY_RUNS="/tmp/run-one /tmp/run-two" \
  SC_TRAJECTORY_OUTPUT=/tmp/symbolic-trajectory.json \
  SC_TRAJECTORY_MARKDOWN=/tmp/symbolic-trajectory.md
```

The command refuses to overwrite either output. It prints the same aggregate
tables written to Markdown and writes the typed per-run plus aggregate JSON.

## Limits

Schema v1 describes preserved host-local observations, not lift. It does not
recover unexposed model sampling seeds, infer token overhead, infer an artifact
handoff without an exact URI, or infer tool intent from prose. The first pilot
smoke is one nondeterministic A/B/C set and cannot support comparative claims.
Repeated experiments, uncertainty estimates, cross-task causal analysis, and
longitudinal storage belong in a later PR.
