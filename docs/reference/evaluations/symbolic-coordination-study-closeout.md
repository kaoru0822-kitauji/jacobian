# Symbolic coordination study closeout

This document closes the five-PR public pilot for
`symbolic-coordination-v1`. It describes a bounded workflow observation, not a
capability-effect claim, benchmark leaderboard, or training-data proposal.

## Architecture and contracts

The stack separates mathematical ground truth from model-visible workflow
state:

- **PR1** owns the immutable 26-case Harbor dataset, public task contracts,
  hidden Oracle material, deterministic fixtures, and independent exact
  verifiers.
- **PR2** owns the host-local ChatGPT-authenticated Codex runner and frozen
  conditions A (no Jacobian), B (Jacobian), and C (Jacobian plus one fixed
  self-audit). It records task, model, prompt, runtime, policy, and source
  bindings before model execution.
- **PR3** independently replays raw JSONL and artifact indexes into typed
  trajectory telemetry. It keeps execution, mathematical acceptance, scope,
  evidence, assurance, and reasoning-protocol observations separate.
- **PR4** owns the resumable paired A/B/C comparison manifest and report. It
  reports exact denominators, Wilson descriptive intervals, paired tables,
  capability use, tokens, wall time, and unavailable cost without causal or
  significance claims.
- **PR5** adds condition D and this final six-family closeout. D uses the same
  PR2 primary prompt, model, reasoning setting, Jacobian policy, and budgets as
  B. A clean-room verifier then emits one typed feedback object, the model may
  make one revision, and a fresh clean-room verification observes the final
  submission.

A/B/C prompt bytes and execution semantics remain unchanged. PR5 extends the
trajectory type to recognize D artifacts but preserves existing A/B/C records
and fields.

## Condition D feedback boundary

The version-1 feedback schema is closed. It contains only:

- an exact task ID, Harbor digest, runtime snapshot ID, initial submission
  digest, and verifier-result digest;
- `ACCEPTED` or `REJECTED` as a checker observation, never a `VERIFIED` claim;
- one-revision limit and fixed certainty label; and
- allowlisted diagnostic code/dimension pairs for mathematical correctness,
  input binding, artifact binding, scope, evidence, assurance, or protocol.

It contains no free-form messages. Hidden solution material, expected
coefficients, Oracle submissions, verifier source, generator internals, secret
paths, and replacement answers are structurally unrepresentable. The runner
recomputes the feedback from the exact isolated verifier result and rejects
unknown fields or codes, stale task IDs, substituted result digests,
unsupported certainty, hidden-material keys, missing revision reports, and
unbound addressed codes. Both verifier invocations occur outside the model
workspace.

## Final observation contract

The final manifest selects exactly one public representative from each pilot
family:

| Family | Representative |
|---|---|
| Valid two-sided inverse | `symbolic-coordination-valid-inverse-01` |
| Perturbed near miss | `symbolic-coordination-near-miss-01` |
| One-direction-only evidence | `symbolic-coordination-one-direction-01` |
| Constant nonzero Jacobian | `symbolic-coordination-keller-only-01` |
| Bounded collision scope | `symbolic-coordination-grid-exhausted-01` |
| Semantic equivalence | `symbolic-coordination-semantic-equivalence-01` |

There is one repetition and four counterbalanced conditions: 24 condition runs
maximum. C and D may each contain their single contractually defined second
model stage. A wrong answer is never rerun. Only a failure classified before
model execution or as infrastructure-incomplete is eligible for an explicit
retry; the final closeout runner intentionally exposes no automatic answer
retry switch.

Before the first model call, the manifest freezes task IDs and Harbor digests,
public and verifier file hashes, all three prompt digests, feedback schema
version, model contract, reasoning level, budgets, runtime and package digests,
source and stack SHAs, CLI contract, and run order. No prompt tuning is allowed
afterward. Non-use of Jacobian, capability failures, incomplete reasoning logs,
and unavailable measurements remain evidence rather than being repaired or
imputed by the analyzer.

## Report interpretation

The typed closeout report keeps initial and final checker acceptance and every
verifier dimension separate. For D it classifies `REPAIR`,
`UNCHANGED_FAILURE`, `REGRESSION`, or `ALREADY_CORRECT` (with explicit
incomplete/unavailable states). It reports A-to-B, B-to-C, B-to-D, and C-to-D
paired tables; condition-level descriptive Wilson intervals; tokens, calls,
wall time, reasoning compliance, and unavailable monetary cost; and one
representative trajectory summary per task family.

These data can establish harness completeness and suggest candidate mechanisms
such as discovery failure, bad input binding, ineffective self-audit, or useful
typed feedback. They cannot establish capability lift, audit lift, feedback
lift, generalization, statistical significance, or a training objective.

## What the public pilot established

The stack establishes that the 26 public mathematical objects are
hand-auditable and independently checkable; A/B/C/D observations can be
replayed against immutable bindings; one-sided inverses, stale or substituted
artifacts, scope escalation, false certification, and timeout/incomplete-search
overclaims fail closed; and external verifier feedback can be bounded to a
leakage-safe typed channel.

It does **not** establish that the selected model reliably discovers or uses
Jacobian capabilities, that self-audit or verifier feedback repairs errors, or
that behavior transfers to unseen polynomial maps. The cases and their
verifier dimensions are now public and therefore contaminated for held-out
model evaluation.

The PR4 pilot observed repeated failure to use Jacobian, incomplete required
reasoning traces, and unchanged self-audit failures. These are workflow
observations, not evidence that the underlying mathematical capabilities are
ineffective. The final PR5 JSON/Markdown report records the six-family D
trajectories and must be cited with its frozen manifest and artifact roots.

## Final bounded observation

The frozen experiment ID is
`sha256:feb57c79f212809ca547be3bb01607e3a8ff5e491585afee6e9e025cbda7e5ac`
at source revision `3fd643acc7cc6af12f18239aa40f3f9db5ff5a26`.
All 24 planned condition runs were collected, with zero pre-model failures,
missing runs, or infrastructure-incomplete terminal records. The final report
ID is
`sha256:d6c69204ec63a8b99de95f6ca3785809bb8ec8b810e905f0a8684107ad7f2ea9`.

Final checker acceptance was 0/6 for each of A, B, C, and D. Each condition's
95% Wilson interval was 0.000–0.390. All four paired tables contained six
both-failed pairs and no discordant pairs. Consequently the observed
acceptance differences for A-to-B, B-to-C, B-to-D, and C-to-D were all zero;
the exact paired values are descriptive only.

Every D initial submission was rejected. Five feedback objects contained only
`REPAIR_INPUT_BINDING`; the semantic-equivalence representative also contained
`CHECK_MATHEMATICAL_CONCLUSION`. One D run applied a revision, but no run moved
to checker acceptance: all six D outcomes were `UNCHANGED_FAILURE`. The
semantic-equivalence revision also reduced evidence validity, illustrating why
the report preserves every verifier dimension instead of treating a revision
as improvement.

No B, C, or D run invoked a Jacobian capability. Required reasoning-log
protocol compliance was incomplete for all 18 Jacobian-enabled runs. Exact
total tokens were 345,505 (A), 930,328 (B), 945,760 (C), and 472,385 (D);
exact total wall times were 305.97, 360.06, 529.37, and 609.55 seconds,
respectively. Monetary cost remained unavailable.

Collection exposed one host-analyzer compatibility defect after the first D
run: D correctly persisted the bound second-stage bytes as
`feedback-prompt.txt`, while the PR3 analyzer expected the C-era name
`audit-prompt.txt`. The completed A/B/D results were not rerun or mutated. The
remaining unexecuted units were collected from the original frozen source with
the same execution functions, and a collection-salvage record preserves that
decision. Artifact-only analysis then used the tested compatibility rule that
accepts the D filename only when `verifier_feedback_digest` exactly equals the
bound `audit_digest`. The rule fails closed for a missing or mismatched alias.

## Reproduction and artifact boundaries

Use the repository commands documented in
[Run agent evaluations](../../how-to/run-agent-evaluations.md). Keep manifests,
raw condition roots, clean-room verifier results, artifact indexes, and reports
outside the repository. A report is reproducible only with its manifest,
source SHA, exact raw roots, and committed schemas; a copied Markdown table is
not sufficient evidence.

For this observation, the host-local artifact root was
`/tmp/jacobian-sc-pr5-closeout-3fd643ac-20260805-live`; the final typed outputs
were
`/tmp/jacobian-sc-pr5-closeout-report-3fd643ac-20260805-final2.json` and the
matching `.md` file. These paths are machine-local handoff locations, not
published benchmark assets.

Oracle submissions, verifier implementation files, generated expected values,
and generator internals stay outside every model workspace. Public task inputs,
instructions, submission schemas, model submissions, typed feedback, and
feedback reports are contaminated after use and must not be repurposed as a
held-out evaluation set.

## Deferred work and capability gaps

The next defensible evaluation would require newly authored held-out cases,
multiple independent repetitions, a preregistered analysis, and enough sample
size to interpret variation. It is intentionally not part of this stack.
Post-solution reasoning-log analysis, a general comparison service, RL/SFT
training, and a larger experiment are also deferred.

The pilot exposed a product gap for a typed polynomial-map composition outcome
with exact input/candidate binding and an independently authorized checker.
That gap is recorded rather than implemented here because the benchmark remains
solvable with existing atomic polynomial capabilities and exact task verifiers.
No new Jacobian product capability, checker authority, task, Oracle, verifier,
or reasoning-log semantics is added by PR5.

RL or SFT is not justified by this pilot: the sample is tiny and public, the
conditions are nondeterministic, no causal benefit has been established, and
the observed failures mix task correctness, input binding, tool discovery,
reasoning-protocol compliance, and audit behavior. Training on these cases
would also destroy their remaining diagnostic value.
