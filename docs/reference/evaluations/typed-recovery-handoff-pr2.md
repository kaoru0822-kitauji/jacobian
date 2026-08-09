# Typed recovery handoff study PR2

This focused host-local observation asks whether typed recovery metadata helps a
weak agent repair a genuine rejected producer-to-checker handoff while preserving
the mathematical candidate and the exact checker boundary. The frozen contract is
[`benchmarks/config/typed-recovery-handoff-pr2.json`](../../../benchmarks/config/typed-recovery-handoff-pr2.json).
No task, prompt, public file, verifier, label, model setting, timeout, or retry
policy changed between conditions.

## Closeout disposition

This pull request now preserves research evidence only. The experimental
diagnostic schema, dispatcher behavior, product documentation, and implementation
tests were removed from the mergeable branch during the final restack. Their
exact historical implementations remain bound by the frozen revisions below;
they are not current product behavior.

The product decision is closed: aggregate acceptance was unchanged at 6/9,
there was only one genuine capability rejection and one typed-recovery exposure
in treatment, and the single positive rejection-to-repair chain is insufficient
to establish repeatable behavioral value. No schema expansion, broader rollout,
or new model execution is authorized by this record. Future work would require a
new independently frozen study with repeated paired handoff opportunities.

The host had no Docker-, Podman-, or Harbor-compatible container runtime. The
existing digest-recording coordination runner therefore copied only public task
files into isolated workspaces, invoked locally authenticated Codex CLI, and ran
the unchanged task-owned verifier in a fresh child process. These are exploratory
host-local observations, not Harbor executions or causal evidence. Raw results are
ignored host evidence under `benchmarks/results/typed-recovery-handoff-pr2-*`.

## Frozen tasks and execution

The task set was frozen before either condition ran. The three tasks were the only
latest saved cases with both difficult terminal behavior and repeated natural
handoff opportunities; other mined tasks primarily failed after successful tool
calls and could not expose diagnostic recovery.

| Dataset and task | Harbor task digest | Verifier bundle digest |
| --- | --- | --- |
| `symbolic-coordination-v1/symbolic-coordination-semantic-equivalence-02` | `3e12d6a7959fdfc475251ac7e2a8ba5e8ca3ccd8868d12157711d981b536e1d2` | `f2434be8f28237142a34b499c99f8615ecfbfc51ff651e5e7119370997941ae1` |
| `symbolic-coordination-v1/symbolic-coordination-semantic-equivalence-03` | `a43b3ff05f551628f6609df3910e63da846309391cb508f48ef0ed478ea27e35` | `f2434be8f28237142a34b499c99f8615ecfbfc51ff651e5e7119370997941ae1` |
| `mathematical-benchmarks-v1/polynomial-map-collision` | `9243ca8ee4800cb8eae039a08e0414c7fcfd8e111c3d1a3c8d6fbbfc44884abd` | `3e16ffac4270bd7567ad1ff565ba725caea918a77327296b4ff27810ccd6cbbb` |

Each condition used three repetitions per task, in declared task order, for nine
rollouts. Both used Codex CLI `0.147.0`, `gpt-5.4-mini`, medium reasoning, a
600-second timeout, workspace-write isolation, disabled web search, required
reasoning logs, and zero wrong-answer retries. The baseline semantic revision was
canonicalization head `b1fcfe25a86eea3b66c3010083d4de21869e7d1d`; its evaluation
worktree revision was `dae51f9732ff350dd8038d8978ac75541aa7572d`. The recovery
evaluation revision was `d098681866e03cd8ad3270f75f08285e1435b28f`, containing
implementation revision `ac771316a9048c7474069688a40f3669b48c2a57`.

The baseline ran from `2026-08-09T10:16:07Z` through `10:40:50Z` in
`jac-recovery-baseline`. Treatment ran from `2026-08-09T10:41:49Z` through
`11:06:19Z` in `jac-recovery-treatment-focused`. The commands used the same
`/private/tmp/typed_recovery_handoff_runner.py`, specification, model, and
`--execute` mode, changing only the root, output directory, condition ID, and
expected revision. The wrapper digest was
`sha256:7f3493c20b37383c414b3570c5bfe1cba4f76a722f49589ea57f04ba2743aaff`;
the reused base runner digest was
`sha256:d4338bfb77e3e5fccfaa149df186a8afc1191b3ef00e8ed916ea8928fd8cb320`.
Both batches completed exactly nine runs with status zero and no outcome reruns.

Inventory mining used `jac-pr928-audit`, `jac-recovery-mining`, and
`jac-recovery-mining-all`. Digest preflight used `jac-recovery-preflight-r2`.
The authoritative post-run parser used `jac-recovery-final-analysis-r2`; its JSON
receipt is `/private/tmp/typed-recovery-final-analysis.json`. The first analysis
session, `jac-recovery-final-analysis`, stopped on formatting before analysis and
did not alter evidence.

## Historical recovery contract

The treatment revision allowed an existing `CapabilityDiagnostic` to carry one
optional closed `CapabilityRecovery` object:

```text
failure_class: REQUEST_VALIDATION
contract_dimension: REQUEST_SHAPE | REQUEST_VALUE
action: REPAIR_REQUEST | REGENERATE_CANDIDATE |
        RETRY_DIFFERENT_INPUT | STOP_NO_CONCLUSION
candidate_reuse: UNASSESSED | REUSABLE | REGENERATE_REQUIRED | NOT_APPLICABLE
compatible_capability_ids: tuple[CapabilityId, ...]
expected_input_type: str | null
reusable_input_path: str | null
retry_input_path: str | null
```

The treatment dispatcher emitted `REQUEST_VALIDATION`, a shape/value classification,
`REPAIR_REQUEST`, `UNASSESSED`, the same factual capability ID, and the advertised
request type after descriptor input validation fails. It advertises a reusable
nested path only when exactly one nested object already contains every required
root field. It does not retry, choose strategy, validate a rejected mathematical
candidate, alter assurance or completeness, relax the checker, or manufacture an
ambiguous reuse path.

## Outcomes

| Condition | Accepted | Rejected | Inconclusive | False certification |
| --- | ---: | ---: | ---: | ---: |
| Canonicalization baseline | 6/9 | 3/9 | 0/9 | 1 |
| Canonicalization and recovery | 6/9 | 2/9 | 1/9 | 0 |

| Handoff metric | Baseline | Recovery |
| --- | ---: | ---: |
| Genuine capability request rejections | 1 | 1 |
| Additional outer `math.run` input rejections | 1 | 0 |
| Typed recovery exposures | 0 | 1 |
| Repair attempts | 1 | 1 |
| Same capability completed after repair | 0 | 1 |
| Exact candidate reuse after structural repair | 0 | 1 |
| Authorized checker completed after repair | 0 | 1 |
| Typed recovery chain reached terminal acceptance | 0 | 1 |
| Repeated identical malformed capability requests | 0 | 0 |

The one positive treatment chain was
`symbolic-coordination-semantic-equivalence-03-r03`. The first
`polynomial.map.inverse.verify` request wrapped one intended coefficient/exponent
term as `{"terms": [term]}`. The capability returned `INVALID_REQUEST` at the
exact nested term path with `REQUEST_VALIDATION`, `REQUEST_SHAPE`,
`REPAIR_REQUEST`, `UNASSESSED`, the compatible capability ID, and expected type
`PolynomialMapInverseVerifyRequest`; it correctly withheld reusable and retry
paths. The agent explicitly distinguished request shape from mathematical
rejection, unwrapped that same term, and retried the same capability. Replacing
only the malformed wrapper in the rejected JSON makes the two payloads exactly
equal, establishing candidate preservation. The authorized checker
`checker://sha256/5155dc4c292561f4997380de7af984e5af0d54c31b8dbb341512d4713048b40f`
returned `VERIFIED` with verification record
`artifact://sha256/eb796d25686bd5cf2296fec98ae434450bb7b9c374b2b4fe95c7adfcc6d96f83`.
The unchanged terminal verifier accepted the submission with no false
certification.

The representative baseline negative was
`symbolic-coordination-semantic-equivalence-02-r02`. A complete inverse request
was embedded under the root `forward_map` value. The capability reported the
missing root fields, but the attempted repair moved `forward_map` outside the MCP
`payload` envelope and failed outer tool validation. The agent never completed
the same capability or checker and eventually built terminal evidence locally.
This is one abandoned, incorrect repair, not a successful candidate reuse.

The collision task supplied terminal negatives rather than recovery
opportunities. Treatment repetitions 1 and 3 completed their mathematical
producer calls but the clean-room verifier rejected the terminal objects;
repetition 2 was mathematically correct but remained
`INCONCLUSIVE/REASONING_PROTOCOL_INCOMPLETE` because it had no unambiguous
reasoning run ID. Recovery metadata cannot repair failures that occur only after
successful producer calls.

Unrelated protocol and transport noise remained material. Baseline had 18 failed
`reasoning.write` calls, seven failed shell commands, two trajectory-extraction
errors, and the one malformed outer `math.run` repair. Treatment had 20 failed
`reasoning.write` calls, three failed shell commands, four trajectory-extraction
errors, and one ambiguous-run-ID terminal finalization. These counts are kept
separate from the genuine capability rejections and are not treated as recovery
cost or benefit.

## Reproducibility handoff

The baseline advertised Jacobian `0.10.0`, 332 capabilities, catalog digest
`sha256:580d277d87a3510a6cd65681f101c3d33d2fed0af1b003e20604d4913c3585fa`,
content digest
`sha256:7a0294067609e9d3bb37cea365910f0b3359adcd4912bb9d96c4ac018db616fd`,
default policy digest
`sha256:870a92b83d3e522e4015b6bb1cabda33086906f9de1c3c36e466251ea7ed1957`,
and surface digest
`sha256:ef985b95db537974b1c55fead285ac447b66f12f5b8cd39a4b6c9bbf458fa42e`.
Treatment advertised the same version, count, and policy digest, with catalog
digest
`sha256:ca5e6924fd1a5695f86ab5cf94c8168c2824bd9ee21bd1b76a2d8ff1b8a9d308`,
content digest
`sha256:899cb5d022a9bcbb3b670b3cd5e4dc22e9faef2ad927de7b9c7be4667404597f`,
and surface digest
`sha256:8e4a006209e6f2e9458e2547c967a58d485f6530e2a0d826f8aa1e75dca58791`.
The sparse polynomial checker was available. Lean and the external `cadical`,
`drat-trim`, and `carcara` executables were absent and were not needed by the
frozen tasks.

Historical implementation validation ran in `jac-pr928-final-gates`: all 30 focused
contract and inverse-composition tests passed, `make check` passed 885 unit tests
plus lint, format, and type checking, and documentation links passed. The
required planner selected the suite fallback because the benchmark configuration
has no exact Python ownership evidence. `jac-pr928-selected-gate` then passed the
unit, domain (185), composition (499 with 2 expected Lean skips), storage (126),
process (234 with 1 platform skip), MCP (54), end-to-end (8 with 1 expected Lean
skip), static, build, and documentation lanes. Its component lane passed 764
tests with 3 platform skips and failed only
`test_carcara_timeout_fails_closed`: a fake checker marker file was absent after
the timeout. `jac-pr928-component-repro` reproduced that exact failure alone.
Neither the test nor its checker implementation differs from `origin/main`, so
this is recorded as an inherited local macOS boundary failure, not recovery
evidence and not a reason to change the study. After upstream removed
implementation-coupled polynomial checker seams, the final restack repeated all
30 focused tests and `make check` with 855 unit tests in
`jac-pr928-main519-final`; both passed.

The raw baseline and treatment directories, batch manifests, exact task and
verifier digests, model and prompt settings, tool surfaces, trajectory JSONL,
reasoning logs, verifier outputs, and analysis receipt are the audit handoff. The
remaining obligations are a container-backed Harbor run and repeated paired
rejection opportunities before any causal or robust behavioral claim. The next
action, if research resumes, is a newly frozen held-out study rather than a rerun
of these outcomes.

## Decision

The compact contract is usable: one genuine rejection produced one exact
repair, preserved candidate, same-capability completion, authorized checker
record, and terminal acceptance. It does not yet have robust behavioral value.
Aggregate acceptance was unchanged, only one treatment rollout exposed recovery,
and the earlier canonicalization-only study also contained a rejection-to-success
trajectory without typed metadata. The focused comparison therefore cannot
attribute the positive event to recovery or establish a repeatable benefit.

No second implementation was attempted. The trajectories justified neither a
looser reuse claim nor a manufactured path, and changing the task or retry policy
would violate the frozen question. PR2 should not merge as a product change; the
smallest defensible outcome is to retain this research record and abandon the
implementation unless a future independently frozen study supplies repeated,
paired handoff opportunities.

The final branch enacts that outcome. Product commit `d8e47bbc` was omitted when
the research commits were restacked on canonicalization head `3b242f64`; the
unique PR2 diff is the frozen configuration and evaluation documentation only.
Historical treatment implementation `ac771316a9048c7474069688a40f3669b48c2a57`
remains recorded for auditability, not as merge-ready code.

Final documentation-only closeout was performed on canonicalization head
`3b242f6487f4d7c1161813747b784b946938e244`. The frozen JSON parsed successfully,
`make docs-linkcheck`, `make test-plan BASE=3b242f64`, and `git diff --check`
passed; the planner classified the unique four-file diff as documentation only.
No model, task, or behavioral evaluation was rerun.
