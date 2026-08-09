# Canonical input and recovery study PR1

This bounded public observation tests two semantic tool changes on three existing
`symbolic-coordination-v1` tasks. The frozen contract is
[`benchmarks/config/canonical-input-recovery-pr1.json`](../../../benchmarks/config/canonical-input-recovery-pr1.json).

The primary outcome is unchanged task-owned exact verifier acceptance. Secondary
diagnostics count valid normalization or checker invocations, request-validation
failures, recovery after a rejected handoff, repeated calls, false certification,
and scope or completeness mistakes. Tool calls receive no reward.

The conditions are latest upstream, upstream plus exact canonical sparse-map input
normalization, and canonicalization plus typed recovery semantics. The third
condition and a recovery PR are conditional: they run only if the first two
conditions show a repeated recoverable handoff failure. Each active condition uses
three rollouts per task with Codex `gpt-5.4-mini`, medium reasoning, no web access,
no wrong-answer retries, and a 600-second timeout.

The host has no Docker-compatible runtime. Runs therefore use the locally
authenticated Codex CLI in isolated public workspaces against a local Jacobian MCP
server, followed by the unchanged clean-room verifier. They are host-local
exploratory observations, not Harbor executions or causal evidence. Raw commands,
timestamps, transcripts, MCP logs, workspaces, verifier records, and manifests are
saved under `benchmarks/results/canonical-input-recovery-pr1-*`.

The existing `polynomial-normalization` task is excluded. Its README declares
`verification_record_schema.json` agent-visible, but its environment Dockerfile
does not copy that file. That benchmark contract must be fixed separately before
the task can provide evidence for checker handoffs.

## PR1 observation

The upstream condition used semantic base `614fdc40511d41bf88607cb0c6cc7c1e6cb91667`
through preregistration commit `00f3e3d5560d3bacf4a4c698542e9512bc6972b5`.
The canonicalization condition used
`bdcdd9712f79942a6e9a975bdf4a67ea4523a29a`. The task, public-bundle, verifier,
model, prompt, timeout, and repetition digests remained frozen by the study
contract.

| Condition | Exact accepted | Rejected | Inconclusive | False certification |
| --- | ---: | ---: | ---: | ---: |
| Upstream | 6/9 | 3/9 | 0/9 | 0 |
| Canonicalization | 6/9 | 1/9 | 2/9 | 0 |

The primary accepted count did not improve. Canonicalization did remove both
observed `INVALID_POLYNOMIAL_MAP_INVERSE_REQUEST` representation failures. It
also enabled two successful exact inverse-checker calls instead of one. In
`symbolic-coordination-semantic-equivalence-01-r03`, the agent passed duplicate,
cancelling, zero, and reordered sparse terms directly to
`polynomial.map.inverse.verify`; the boundary stored canonical maps and the
independent checker returned `VERIFIED`. Generic outer-request shape failures
remained: three `INVALID_REQUEST` calls were observed in each condition.

One canonicalization rollout, task 2 repetition 2, was interrupted externally
after it began. It was preserved as `INCONCLUSIVE/INFRASTRUCTURE_FAILURE`; the
model was not rerun. Task 3 repetition 1 produced a mathematically correct
terminal object, but its reasoning run IDs were ambiguous, so the finalizer
correctly recorded `INCONCLUSIVE/REASONING_PROTOCOL_INCOMPLETE`. These outcomes
explain why the raw 6/9 acceptance count must not be restated as 6/7 without an
explicit complete-case qualifier. Six canonicalization trajectories also
reported noncanonical trajectory-value extraction errors in the observational
runner; terminal verification and raw traces remain available, but those
secondary extracted values are not evidence.

## Recovery rationale and handoff

The repeated failure justifying the separate recovery condition was a checker
handoff shape error, not a mathematical rejection. In upstream task 2 repetition
3, the agent embedded `inverse_map` and both variable lists inside the
`forward_map` object, received a root `required` failure, repeated the same
nesting, and then did it a third time. The run eventually passed only after
abandoning that checker path and constructing the terminal certificate locally.
Existing prose listed missing fields, but did not encode stable failure class,
contract dimension, candidate-reuse state, or expected request type. This is the
bounded target for PR2; reasoning-log write errors and strategy choices are out
of scope.

The installed upstream surface advertised Jacobian `0.10.0`, 332 capabilities,
catalog digest
`sha256:1b92becedb2ea91df037614cf12a3f7e22fa05b926c043e666ef96610e79851a`,
content digest
`sha256:84eefb7287eb623717839c65c34c91b9f9c3ac67668203aad6f5d7a94beb4ad8`,
default policy digest
`sha256:870a92b83d3e522e4015b6bb1cabda33086906f9de1c3c36e466251ea7ed1957`,
and surface digest
`sha256:c3ad3f2264850e8925122aa6beeaa577512bf9cbf2b7d52f083ac502e7cec4f8`.
The canonicalization surface digest was
`sha256:455d6cde933acdd0cfdfabf55090f5aeff9ad587b57272662e77fde1f7203228`.
The sparse polynomial checker was available; Lean and external proof executables
were absent and were not needed by these tasks.

Raw evidence is under
`benchmarks/results/canonical-input-recovery-pr1-upstream` and
`benchmarks/results/canonical-input-recovery-pr1-canonicalization`. The named
sessions were `jac-canonical-upstream`, `jac-canonical-treatment`, and
`jac-canonical-resume-2`; the failed drift-check-only resume attempt was
`jac-canonical-resume`. Session logs are
`/private/tmp/jac-canonical-upstream.log`,
`/private/tmp/jac-canonical-treatment.log`,
`/private/tmp/jac-canonical-resume.log`, and
`/private/tmp/jac-canonical-resume-2.log`. The successful focused implementation
validation before this observation was 37 tests in the relevant contract and
composition files plus one exact-rational capability test. Final PR validation
is recorded in the pull request checks. The unresolved obligation is a held-out
or Harbor execution before making a causal claim; the next action is the frozen
canonicalization-plus-recovery condition.

## Engineering closeout

The accepted canonicalization mechanism was rebased without an experimental
rerun onto upstream `0052a5bf78f63f5539be13da6493abb395c5026d`. Review hardening
now validates a structural representative of every complete canonicalizing
request before duplicate-coefficient accumulation, caps each coefficient
involved in an accumulation at 256 digits, caps each duplicate group at 64
terms, and validates the exact combined request again. A validation context
keeps structural and cross-field invariants active while deferring only
support-dependent operation semantics until after exact cancellation. This
preserves canonical candidate and artifact identity, accepts representations
whose out-of-budget terms cancel, and fails closed before unbounded duplicate
arithmetic or artifact writes.

The final-tree focused lane passed 48 contract, inverse-composition, and identity
boundary tests in tmux session `jac-pr920-review-hardening-r3`. `make check`
passed 872 unit tests plus the repository lint, format, and type gates in session
`jac-pr920-check`. The earlier `jac-pr920-review-hardening` failure exposed and
preserved one boundary-projection bug in the new guard; its rerun was not a model
rollout and did not alter the frozen study outcomes. After the final upstream
restack, the same 48-test lane passed again in `jac-pr920-latest-final`, and
`make check` passed 884 unit tests plus lint, format, and type checking in
`jac-pr920-latest-check`. The final checker-seam restack passed the 48 focused
tests and `make check` with 854 unit tests in `jac-pr920-main519-final`.
After rebasing onto `71fa917c`, the two final review findings were reproduced and
covered by the focused lane: cancelled degree-33 terms no longer trigger the
degree-32 operation budget, and a 65-term duplicate group is rejected before
coefficient accumulation. The final focused lane contains 56 tests, including
the interval-verification seam exposed by the broad gate; no model rollout was
rerun.

The final `make test-changed BASE=origin/main` runs passed unit, domain,
composition, storage, process, MCP, end-to-end, static, build, and documentation
lanes. Their component lanes had unrelated macOS timeout-marker failures in one
or both of `test_carcara_timeout_fails_closed` and
`test_drat_timeout_fails_closed`; the branch changes neither checker nor test,
and the DRAT failure also reproduced in isolation. This is retained as an
upstream/environment obligation rather than folded into the canonicalization
change.
The final non-overlapping restack onto `0052a5bf` passed the 56 focused tests,
`make check` with 856 unit tests, documentation link checking, test planning,
and `git diff --check`.
The last review pass generalized full-request preflight beyond inverse
verification and added an evaluation-dimension regression proving cross-field
failure precedes duplicate accumulation. Its expanded focused lane passed 65
tests, and `make check` again passed 856 unit tests plus lint, format, complexity,
and type checking. No model rollout was rerun.

## PR2 recovery observation

The combined condition used recovery implementation revision
`45a6241b9cda98d8edc07dcb89107561f6445a7e`. It attaches one optional, closed
`recovery` object to the existing diagnostic. The object separates request
validation from a mathematical conclusion, request shape from request value,
the permitted local action, candidate-reuse state, compatible capability IDs,
and expected input type. It may advertise an exact nested-input move only when
one nested object factually contains every required root field. It does not
execute the move, validate nested mathematical values, select another
capability, or change completeness, assurance, or checker authorization.

| Condition | Exact accepted | Rejected | Inconclusive | False certification |
| --- | ---: | ---: | ---: | ---: |
| Upstream | 6/9 | 3/9 | 0/9 | 0 |
| Canonicalization | 6/9 | 1/9 | 2/9 | 0 |
| Canonicalization and recovery | 7/9 | 0/9 | 2/9 | 0 |

The combined condition had one model timeout and one ambiguous reasoning-run-ID
failure. Its seven remaining rollouts were accepted by the unchanged exact
terminal verifier. This is one more raw acceptance than either earlier
condition, but the observation is not paired causal evidence and the two
inconclusive outcomes must remain in the denominator.

Four capability-schema rejections carried typed recovery: three inverse-check
requests and one Jacobian request. The Jacobian trajectory, task 3 repetition 2,
classified a malformed coordinate as `REQUEST_SHAPE` with action
`REPAIR_REQUEST`, then corrected the input and completed the same capability.
Canonicalization alone also contained one rejection-then-success trajectory, so
the event is evidence that the contract is usable, not evidence that it caused
the recovery. In task 2 repetition 2, the agent explicitly distinguished a
shape failure from a mathematical rejection and stopped after one rejected
capability call; the analogous upstream trajectory repeated the same rejection
three times. It still finished by local replay because reasoning-log errors
blocked its planned checker retry.

The harder negative case was a request whose `inverse_map` and variable fields
were embedded inside the `forward_map` value. The diagnostic honestly reported
`REQUEST_SHAPE`, `REPAIR_REQUEST`, `UNASSESSED`, and the expected request type,
but withheld a reusable path because moving that value unchanged would still be
invalid. The agent did not complete a corrected checker handoff. No recovery
rollout reintroduced a strict sparse-representation failure, but total tool
errors increased from 24 in canonicalization to 50 because of unrelated
`reasoning.write` and MCP-parameter failures. The recovery tweak therefore has
no demonstrated overall cost reduction or robust checker-handoff improvement.

The recovery surface advertised 332 capabilities, catalog digest
`sha256:092432d64c583518d30b9afff626de240ab504bf66a8baffd8688a38db58f0fa`,
content digest
`sha256:c410428de4279daf10e00789d6137b932b48a0890711e935e276f4edb8152488`,
unchanged default policy digest
`sha256:870a92b83d3e522e4015b6bb1cabda33086906f9de1c3c36e466251ea7ed1957`,
and surface digest
`sha256:df8ba288231a55f6b8fa03520bcb1e52caf9a37dcca1ad4c502e0222d4b81f14`.
Raw evidence is under
`benchmarks/results/canonical-input-recovery-pr1-canonicalization-recovery`.
The successful named session was `jac-recovery-treatment-2`, with log
`/private/tmp/jac-recovery-treatment-2.log`. The earlier
`jac-recovery-treatment` launch failed before model execution because its
expanded expected revision was mistyped; it created no result tree and is
preserved in `/private/tmp/jac-recovery-treatment.log`.

Focused implementation evidence includes 10 contract tests in
`jac-recovery-contracts-2` and all 18 polynomial inverse composition tests in
`jac-recovery-polynomial-file-2`. The first full-file attempt exposed and
preserved a test-fixture mistake: a cross-field domain error was incorrectly
expected to carry generic schema-boundary recovery. After changing that fixture
to an actual canonical-integer pattern violation, the final file passed. The
remaining research obligation is a held-out or Harbor comparison that isolates
recovery from reasoning-log reliability and samples more actual rejected
producer-to-checker handoffs.

This earlier observation is retained as historical mechanism evidence. The
subsequent frozen focused comparison is recorded in
[`typed-recovery-handoff-pr2.md`](typed-recovery-handoff-pr2.md): aggregate
acceptance remained unchanged, only one treatment rollout exposed typed
recovery, and the final PR2 branch removed the experimental product code. No
schema or dispatcher change is proposed by this record.
