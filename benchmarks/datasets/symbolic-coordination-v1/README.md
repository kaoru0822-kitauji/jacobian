# Symbolic coordination v1

This versioned Harbor dataset is the issue #477 PR1 contract and
hand-auditable polynomial-map pilot. Its 26 independently runnable cases test
terminal exact certificates without requiring Jacobian or prescribing a tool
sequence.

## Pilot families

| Family | Cases | Contract focus |
| --- | ---: | --- |
| Valid two-sided inverse | 5 | Both exact ordered compositions vanish |
| Perturbed near-miss | 4 | A plausible inverse has a nonzero residual |
| One-direction-only evidence | 3 | Supplied partial checking is not authoritative |
| Constant nonzero Jacobian | 4 | Keller condition is separated from global invertibility |
| Bounded collision scope | 6 | Witnesses, grid exhaustion, timeout, and incomplete search |
| Semantic equivalence | 4 | Renaming, reordering, duplicate terms, and cancellation |

Every task freezes one offline `input.json`, a strict submission schema, a
hidden Oracle solution, and a task-local clean-room verifier. The verifier uses
only Python's standard library and independently replays rational polynomial
normalization, both map compositions, Jacobian determinants, finite grids, and
collision witnesses. It also binds the exact input, claim, map, subject,
semantics, scope, checker identity, evidence path, and evidence digest.

The pilot caps submissions at `CHECKED`. No operator-authorized Jacobian
checker record is part of PR1, so a `VERIFIED` claim is false certification and
receives zero reward. A constant nonzero Jacobian does not itself license a
global-invertibility claim. Grid exhaustion licenses only the declared finite
scope, while timeout, cancellation, incomplete work, and missing witnesses
remain non-conclusions.

## Deterministic identity

`generate.py` deterministically renders the 26 bundles from authored exact
fixtures. `pilot-manifest.json` binds the generator/case version, family,
fixture digest, and subject digest for every member. Regeneration is checked by:

```sh
uv run --locked python benchmarks/datasets/symbolic-coordination-v1/generate.py --check
```

An immutable evaluation snapshot is intentionally deferred until an operator
freezes the later comparison design; repository policy does not create a
snapshot merely for task authoring. Existing `agent-workflow-v1` snapshots are
unchanged.

## Validation

```sh
make harbor-plan BASE=origin/main
make harbor-check-task DATASET=symbolic-coordination-v1 TASKS="<task ids>"
make harbor-oracle-task DATASET=symbolic-coordination-v1 TASKS="<task ids>"
make harbor-check
```

The dataset contract itself contains no comparison job, model run,
post-solution audit, reasoning-log analysis, or training contract. The
host-local PR2 observation runner below is operator tooling around this public
contract; it does not change any task or add a mathematical capability.
Product-surface observations that did not block the pilot are recorded in
[deferred capability gaps](CAPABILITY_GAPS.md).

## Host-local Codex pilot

The PR2 runner executes one public member through an existing file-backed
Codex CLI ChatGPT login, with no Docker and no LLM API key. It freezes the task,
prompt, `gpt-5.3-codex-spark` model contract, `medium` reasoning effort, budgets,
sampling semantics, source revision, and public/verifier digests into one
read-only runtime snapshot shared by all requested conditions:

- **A:** no Jacobian MCP and no post-solution audit;
- **B:** Jacobian MCP with reasoning-log mode `REQUIRED`, no audit;
- **C:** the same Jacobian primary run followed by exactly one fixed,
  non-Jacobian contract-audit pass and at most one coherent revision.

Condition C is not Jacobian's reasoning-log mode named `AUDIT`. The model sees
only `input.json`, `instruction.md`, `submission_schema.json`, and an empty
`evidence/` directory at startup. A deny-by-default Codex permission profile
blocks reads outside that fresh workspace and disables shell networking; web
search is separately disabled. Verification runs later in a fresh child
interpreter against the task-owned clean-room verifier outside the model
workspace. The host adapter maps Harbor's `/app/submission.json` to
`./submission.json` in the isolated model workspace and copies it into the
verifier's separate `/app` tree only after the model exits.

Run the preflight and review a no-model dry run before opting into execution:

```sh
unset OPENAI_API_KEY JACOBIAN_MODEL
make symbolic-coordination-codex-preflight \
  SC_CODEX_TASK=symbolic-coordination-near-miss-01
make symbolic-coordination-codex-dry-run \
  SC_CODEX_TASK=symbolic-coordination-near-miss-01 \
  SC_CODEX_OUTPUT=/tmp/symbolic-coordination-codex-dry-run
make symbolic-coordination-codex-eval EVAL_EXECUTE=1 \
  SC_CODEX_TASK=symbolic-coordination-near-miss-01 \
  SC_CODEX_OUTPUT=/tmp/symbolic-coordination-codex-smoke
```

The output must be outside the repository and initially empty. It preserves
the immutable snapshot, redacted preflight, exact command plans, raw Codex
JSONL/stderr, stage timing and telemetry, pre-audit and final submissions,
audit report/revision, external verifier result, Jacobian state, validated
reasoning-log JSONL exports, and a content-addressed artifact index. A wrong or
contract-invalid mathematical answer is a completed `REJECTED` observation;
auth, model/task/source drift, timeout, missing usage/output, contamination,
or verifier infrastructure failure makes the run `INCOMPLETE`.

PR3 also preserves a clean-room verifier result for the initial submission,
before condition C's audit, and provides a fail-closed operator telemetry
command:

```sh
make symbolic-coordination-trajectory-telemetry \
  SC_TRAJECTORY_RUNS="/tmp/symbolic-coordination-codex-smoke" \
  SC_TRAJECTORY_OUTPUT=/tmp/symbolic-trajectory.json
```

It verifies the raw artifact index and emits typed trajectory schema v1 JSON
plus Markdown A/B/C tables. Mathematical correctness, evidence validity, scope,
assurance, infrastructure, and trajectory diagnostics remain separate. The
rules and unavailable-data semantics are documented in
[the telemetry reference](../../../docs/reference/evaluations/symbolic-coordination-trajectory-telemetry.md).

Codex CLI 0.146.0 does not expose seed or temperature controls for ChatGPT
login runs, so the snapshot records those fields as unavailable and the run as
nondeterministic. Token accounting is enforced at the stage boundary after
Codex reports usage. The runner currently requires the local ChatGPT session
to use Codex's file-backed credential store so it can create an ephemeral
auth-only `CODEX_HOME`; credential material is never copied into result or
model workspaces.
