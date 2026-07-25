# Agent evaluations

[Documentation home](../index.md)

## Purpose

Jacobian is useful only if it changes research behavior, not merely if its APIs
work. Model-in-the-loop evaluations test whether a model with access to the
kernel is better at:

- attacking its own candidate with complete semantics;
- distinguishing evidence from verified results;
- using structured witnesses to repair or abandon an idea;
- reducing a discovery without breaking it;
- selecting and verifying representation changes;
- handing another researcher a compact replayable bundle.

These evaluations are downstream product tests. They do not replace checker
conformance, and a model's correct answer does not validate the kernel.

## Experimental conditions

Each scenario compares at least:

1. **Baseline:** the same model and task without Jacobian tools.
2. **Kernel:** the same model and task with the release-appropriate Jacobian
   tools.

Hold constant:

- model and model version;
- system and task instructions except for tool availability;
- public repository snapshot;
- time, token, and compute budgets;
- random-seed policy;
- external knowledge cutoff;
- number of attempts.

Use multiple seeds and report every run. Do not select the best transcript.
When model versions change, establish a new baseline rather than combining
incomparable results.

## Eval-case contract

Every case contains:

- stable ID, title, version, and owner;
- frozen public task artifacts;
- declared baseline and kernel conditions;
- hidden oracle and independently replayable expected facts;
- one critical discriminator;
- at least one tempting but wrong path;
- explicit allowed tools and budgets;
- scoring rubric and hard-failure rules;
- known alternate valid solution paths;
- contamination risks and cutoff metadata;
- reviewer handoff requirements;
- provenance for task, artifacts, model, and tool versions.

The hidden oracle is not available in the candidate workspace. It should be
small enough for an independent evaluator to replay and must not depend on the
model's explanation.

## Scoring

Correctness gates efficiency. A run fails regardless of total score if it:

- reports an unsupported verified mathematical conclusion;
- converts timeout, cancellation, error, restricted coverage, or sampling into
  truth or falsehood;
- accepts evidence bound to the wrong claim, semantics, candidate, encoding, or
  scope;
- claims a stronger transformation relation or minimality class than was
  checked.

For runs that pass the hard gate, the initial rubric is:

| Dimension | Weight | Evidence |
| --- | ---: | --- |
| Mathematical and semantic correctness | 40 | Matches the hidden oracle and respects the quantified domain |
| Evidence and verification discipline | 25 | Uses the correct witness/checker/certificate path and preserves assurance labels |
| Critical discriminator | 15 | Notices the scenario's central trap or representation issue |
| Validation and recovery | 10 | Tests plausible alternatives and recovers from refuted candidates |
| Reviewer handoff | 5 | Produces a concise artifact-linked result another process can replay |
| Efficiency | 5 | Tool calls, tokens, time, and compute, considered only after correctness |

Weights may change after a pilot, but hard-failure rules do not. Report both the
weighted score and the underlying outcome fields.

Primary aggregate metrics are:

- single-run pass rate;
- catastrophic false-certification rate;
- verified-witness utilization rate;
- successful recovery rate after a defeating witness;
- replayable-handoff rate;
- tokens, tool calls, wall time, and compute conditional on correctness;
- tool execution errors and parameter/schema errors per run.

The public MCP pilot records elapsed time, token usage, tool-call count, tool
errors, parameter errors, correctness, and a conservative false-certification
flag in each result. A claimed verified result that fails durable scoring is
counted as false certification for triage, even when the immediate cause may
later prove to be a reporting or binding error.

The initial target for catastrophic false certification is zero. Other release
thresholds are set only after baseline pilots show the scenario is
discriminating rather than impossible or trivial.

## Initial scenario suite

The public motifs and exact facts underlying these evaluations are listed in
the [Mathematical scenario catalog](math-scenarios.md). Agent-facing cases use
held-out relabelings, parameter changes, and distractors rather than exposing
those public answers directly.

The runnable public pilot also includes `GRAPH-ATLAS-PATH-001`, a smoke case
for the first graph capability slice. It requires separate
`graph.search.atlas` and `graph.compute.properties` calls, accepts any labeling
of the five-vertex path, checks the durable graph-to-property relationship, and
fails a run that promotes exact NetworkX computation to verified evidence.
This public case validates the harness and tool composition; it is not a
held-out research benchmark.

### EVAL-SEM-001 — Complete semantics

**Release:** v0.2

The public candidate describes intended legal objects but the underlying
structure induces an additional legal object that defeats it. The names and
topology should be synthetic variants, not a copy of a published benchmark.

The critical discriminator is whether the agent asks the oracle to attack the
candidate under the declared complete semantics and then uses
`witness.verify`. A tempting wrong path evaluates only the listed objects and
reports a positive result.

The hidden oracle contains the minimal unexpected object and an independent
direct-witness replay.

### EVAL-TRUST-002 — Operational failure is not a conclusion

**Release:** v0.2

An evaluator or oracle times out after returning partial promising evidence.
The critical discriminator is preserving `execution = TIMEOUT`, incomplete
coverage, and an unverified conclusion. A tempting wrong path describes the
absence of a found witness as proof of nonexistence.

### EVAL-BIND-003 — Evidence substitution

**Release:** v0.2

The workspace contains a valid certificate for a nearby candidate and an
uncertified target candidate. Payloads are similar enough to invite reuse.

The correct behavior is to call `certificate.verify`, observe the binding
failure, and leave the target unverified. The hidden oracle records every
binding dimension and the valid source certificate.

### EVAL-SHRINK-004 — Checked minimization

**Release:** v0.2

A large counterexample contains redundant elements and at least one attractive
reduction that breaks the predicate. The agent should use `shrink.run`, retain
only checked steps, report the achieved minimality class, and hand off the
accepted-step trace.

Score minimality only within the declared reducer set and budget. Do not require
one canonical human-preferred form when several incomparable minima exist.

### EVAL-XDOM-005 — Domain independence

**Release:** v0.2

Give the agent a non-graph reference plugin with a different witness type. The
task checks whether it uses generic artifacts and verification tools rather
than assuming paths, vertices, or graph canonicalization.

### EVAL-TRANS-006 — Transformation direction

**Release:** v0.2

Two proposed transformations are available: one is an equivalence and one is
only an over-approximation or restriction. Both yield an attractive derived
result.

The agent must distinguish `transform.apply` from `transform.verify`, discharge
the appropriate proof obligation, and avoid transporting a conclusion in an
invalid direction.

### EVAL-ENUM-007 — Exhaustive bounded search

**Release:** v0.2

An enumeration reaches either its true finite scope or a configured limit. The
critical discriminator is whether the agent uses the scope certificate and
reports exhaustive coverage only in the former case.

### EVAL-RESUME-008 — Search lineage under failure

**Milestone:** M3

A long-running experiment is interrupted after producing useful candidates and
failed branches. The agent should resume from the experiment handle, preserve
lineage, avoid double-promoting duplicate candidates, and route final evidence
through v0.2 verification.

### EVAL-REPAIR-009 — Nearby claim repair

**Milestone:** M4

A verified counterexample defeats the original claim. The agent should propose
nearby statements, falsify easy failures, and return survivors as hypotheses
with exact assumption changes. None becomes certified merely because search
did not refute it.

### EVAL-GENERALIZE-010 — Parameter regions preserve uncertainty

**Milestone:** M4

A verified finite construction supports a proposed parameter family. The agent
must separate proved necessary and sufficient conditions from sampled and
unknown regions, then send any proof-bearing claim through its checker.

### EVAL-MEM-011 — Temporal provider retrieval

**Milestone:** M5

An optional corpus provider contains relevant material before and after a
declared historical cutoff. The agent must retrieve useful pre-cutoff episodes
without using later results, preserve trust labels, and continue safely if the
provider is absent.

### EVAL-ABS-012 — Abstraction remains a hypothesis

**Milestone:** M5

Several retrieved failures share a likely obstruction, while a minority fail
for another reason. The agent may use `episode.compare` or
`abstraction.extract`, but must state the proposed abstraction as a hypothesis
and test it against held-out instances.

### EVAL-HANDOFF-013 — Independent replication

**Release:** v1.0

The agent must export the minimal artifact, claim, semantics, evidence,
checker, and provenance set needed by an independent installation. The reviewer
gets only that declared bundle and must reproduce the verification outcome
offline.

## Benchmark construction

### Frozen public artifacts

Candidate-facing artifacts are immutable and identified by digest. Freeze:

- repository commit;
- task prompt;
- installed plugin and checker manifests;
- available resource set;
- dependency lock;
- model/tool configuration;
- public knowledge cutoff.

The hidden oracle has a separate identity and storage location. Evaluated agents
must not have filesystem, retrieval, or network access to it.

### Contamination control

Published mathematical episodes are useful design sources but weak hidden
tests. Exact published examples may be recalled or retrieved. Prefer generated
or hand-designed structural variants that preserve the trap while changing
surface form.

Keep evaluation fixtures out of public implementation documentation and model
training exports. Record whether a scenario or close analogue has appeared in:

- repository docs and issues;
- public benchmark suites;
- published papers or blog posts;
- prior model prompts;
- training-data exports.

Temporal research evaluations enforce the cutoff in both retrieval indexes and
public artifacts. A post-cutoff citation is a contamination failure even if the
mathematical answer is correct.

### Alternate valid paths

Rubrics score outcomes and evidence, not one hidden chain of tool calls. An agent
may find a valid direct witness, derive an equivalent checked certificate, or
reject a candidate earlier through a sound validation rule. The oracle records
known alternatives and reviewers may accept a new route only after independent
replay.

### Reviewer handoff

Every passing run produces a compact handoff containing:

- exact claim and candidate URIs;
- conclusion and full assurance fields;
- witness or certificate URI;
- verification-record and checker digests;
- declared scope, limits, and remaining uncertainty;
- enough provenance for clean-process replay.

The reviewer does not need the full conversation transcript. This prevents a
persuasive narrative from substituting for evidence.

## Eval development workflow

1. Start from a real failure mode or release invariant.
2. Define the critical discriminator and tempting wrong path.
3. Build and independently test the hidden oracle.
4. Freeze public artifacts.
5. Run a no-tool baseline and confirm the case is neither universally trivial
   nor impossible.
6. Run the kernel condition over multiple seeds.
7. Review hard failures before interpreting efficiency.
8. Revise ambiguous prompts or oracles, not scores after seeing a favored
   model's answer.
9. Version the case whenever public artifacts, oracle, rubric, or allowed tools
   change.

Model evaluations are reported as empirical capability evidence. They never
upgrade a conjecture, transformation, witness, or certificate to verified
status.

## Executable known-answer pilot

`benchmarks/agent_mcp.py` runs the public `PATH-CLOSURE-001`,
`MAT-KERNEL-001`, `GRAPH-BIP-TRUE-001`, `LEAN-NAT-INDUCTION-001`, and
`LEAN-SQRT2-001` cases, plus the bounded `ERDOS-STRAUS-001` research pilot,
through a real Codex CLI using the project
`jacobian_local` MCP profile. Each case receives an isolated state directory.
The runner retains the raw JSONL transcript and structured agent report, then
scores the durable verification record, evidence, exact bindings, claim, and
candidate directly from the Jacobian store. Lean cases additionally bind and
score the selected runtime environment and declared trust base.

`GRAPH-BIP-TRUE-001`, the Lean cases, and `ERDOS-STRAUS-AB-001` are
runner-level agent cases defined by the benchmark harness. They are not
component fixtures in the [mathematical scenario catalog](math-scenarios.md);
that catalog remains the source for the shared mathematical objects they reuse.

Every agent report also records structured observations in four non-scoring
categories: useful tooling, tooling gaps, domain-knowledge gaps, and concrete
improvements. The runner writes these observations to a per-case
`feedback.json`. Feedback is empirical input for tool design; it is not
mathematical evidence and cannot affect the durable correctness score.

Descriptor sizes, transcripts, timing, and token measurements are run
artifacts, not reference contracts. Store them under the ignored
`benchmarks/results/` directory and summarize them only from a clean,
identified tree when making a benchmark claim.

Run the kernel condition with:

```sh
uv run python benchmarks/agent_mcp.py
```

The runner explicitly fixes Codex reasoning effort to `medium` by default and
records it in run metadata. Use `--reasoning-effort high` only as a separately
reported condition; otherwise a user's global Codex setting makes token and
latency comparisons ambiguous.

This is an initial known-answer integration pilot, not the held-out comparative
evaluation described above. It currently has no no-tool baseline, model seed
control, hidden oracle, or multi-attempt aggregate. Results must therefore be
reported per run and must not be used as a capability or performance claim.

## Executable capability A/B pilot

`benchmarks/agent_ab.py` implements the control/treatment comparison separately
from the integration pilot. It launches Codex with `--ignore-user-config` so a
personal or project MCP server cannot leak into the control condition.

For every case and repetition:

- control receives an empty writable workspace, no MCP configuration, and may
  construct its own local computation;
- treatment receives the same task and model settings plus only the compact
  `capabilities` MCP profile;
- condition order is shuffled from a recorded seed;
- both conditions use the same structured report schema and independent
  known-answer scorer;
- treatment verification records and exact finite evidence are replayed from
  its isolated Jacobian state;
- raw transcript, stderr, report, usage, MCP calls, shell calls, generated-file
  count, and elapsed time are retained;
- the summary reports per-condition pass rate and paired token, time, shell,
  and MCP-call deltas.

Run the default three-pair pilot with:

```sh
uv run python benchmarks/agent_ab.py --case ERDOS-STRAUS-AB-001
```

The initial public case is an executable harness check, not a sufficient
product claim. Product conclusions require multiple held-out cases and
repetitions. Report all runs, use paired deltas, and reject any treatment that
improves efficiency by increasing unsupported mathematical conclusions.

Development pairs may validate the harness or reveal interface problems, but
they are not product evidence. Keep their reports with the run artifacts.
Publish a comparative result only when the protocol's held-out-case,
repetition, contamination, and independent-scoring requirements are met.
