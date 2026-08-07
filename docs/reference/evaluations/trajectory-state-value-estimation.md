# Observable trajectory-state value estimation

[Documentation home](../../index.md) · [Evaluation methods](evaluation-methods.md)

This research surface tests whether Jacobian's typed mathematical runtime plus
the model-authored external reasoning log can provide a cheap, interpretable
state abstraction for offline value estimation. It borrows the milestone idea
from [Numca and Hista](https://arxiv.org/abs/2605.29782), but does not use model
hidden states, train a critic, update model weights, or authorize mathematical
assurance.

The work is staged. This first contract defines extraction only. Clustering,
offline value estimation, observation-only scoring, and repeated Codex
experiments belong to later stages.

## Version 1 state contract

[`trajectory-state-v1.schema.json`](schemas/trajectory-state-v1.schema.json)
is generated from the closed Pydantic contract in
`jacobian.eval.trajectory_state`. An extraction binds the raw Codex JSONL by
SHA-256, the task family, ordered state snapshots, optional clean-room terminal
evidence, and the fixed declaration `assurance_authority = false`.

Each snapshot contains:

- a hard state: typed inline objects and artifacts, candidate and checker
  state, open and discharged obligations, execution, completeness, assurance,
  scope, binding validity, scope-escalation errors, the latest meaningful
  transition, and reasoning-protocol state;
- an optional soft state containing only PLAN, latest AFTER_TOOL, and FINAL
  external summaries authored by the model; and
- its observation boundary, hard-state digest, changed fields, eligible
  milestone kinds, and an explicit eligibility reason.

The soft state is observable external text. It is not hidden chain-of-thought.
It is not used to decide milestone eligibility.

## Extraction and anti-hacking semantics

The deterministic extractor accepts completed Codex MCP events. A successful
`reasoning.write` creates PLAN, AFTER_TOOL, or FINAL observation boundaries.
A `math.run` completion creates a TOOL_RESULT boundary and reads only the typed
capability result: output, artifacts, obligations, diagnostics, scope,
completeness, and assurance. Rejected reasoning writes do not exist in the
durable reasoning log and are ignored.

A boundary is an eligible milestone only when at least one of these typed
changes occurs:

- a new mathematical object, artifact, candidate, or repaired candidate;
- checker acceptance or rejection;
- an obligation opens or is discharged;
- independently verified evidence makes a binding valid, or diagnostics make
  one invalid;
- scope changes or a scope escalation is rejected; or
- completeness or assurance changes.

The following invariants are enforced:

- a tool invocation is never a milestone by itself;
- repeated identical outputs, artifacts, candidates, and statuses add no
  milestone;
- longer or rewritten summaries add no milestone;
- TIMEOUT, CANCELLED, ERROR, missing results, and incomplete search do not
  materialize claimed output objects;
- checker acceptance and `VERIFIED` assurance remain separate; a candidate is
  recorded as verified only when the typed result has `VERIFIED` assurance and
  a verification-record binding;
- clean-room terminal acceptance is a separate label, never intermediate
  assurance and never a milestone reward; and
- the extractor cannot mutate Jacobian state or mathematical assurance.

Malformed JSONL fails closed. Closed models reject unknown fields. A terminal
label marked TIMEOUT, CANCELLED, or ERROR must be INCONCLUSIVE.

## PR1 real-trajectory observation

The immutable sample under
[`pr1-gcd-real-codex`](../../../tests/unit/tooling/fixtures/trajectory_state/pr1_gcd_real_codex/manifest.json)
was collected on source revision
`86666f6fc27564bbc32f6e652b64a5f4ca50940e` with Codex CLI 0.147.0,
`gpt-5.4-mini`, medium reasoning effort, a read-only workspace, and REQUIRED
reasoning logs. The manifest binds the exact prompt, catalog and policy
digests, raw Codex JSONL, exported durable reasoning log, stderr, and extracted
record.

Manual inspection found four states:

| Boundary | Eligible | Typed change |
| --- | --- | --- |
| PLAN | no | protocol and soft summary only |
| TOOL_RESULT | yes | exact gcd object, declared scope, COMPLETE coverage, COMPUTED assurance |
| AFTER_TOOL | no | protocol and soft summary only |
| FINAL | no | protocol and soft summary only |

The model first made a rejected PLAN call with an extra field, recovered, and
completed a valid reasoning cycle. That failure changed the design: only
successful durable reasoning writes may create states. The one real sample is
a parser and interpretability check, not evidence of predictive value. It has
no clean-room terminal verifier label, so it cannot enter the later value
comparison as a labelled evaluation row.

## Current limitations

Version 1 deliberately uses conservative generic output interpretation. A
non-empty typed capability output becomes one content-addressed object, while
candidate-like fields receive a separate candidate identity. Domain-specific
semantic equivalence is not inferred. Evidence binding becomes valid only from
verified checker evidence or clean-room terminal evidence; ordinary
reasoning-call protocol binding is not mathematical progress.

The contract has not yet established that its state dimensions predict
continuation success. PR2 must compare group, Numca-like numerical, text-only,
typed-only, and hybrid estimators on frozen labelled trajectories. Any change
to extraction after labels are inspected requires a new schema or experiment
boundary.
