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
3, the agent placed the entire four-field inverse-check request under
`forward_map`, received a root `required` failure, repeated the same nesting, and
then did it a third time. The run eventually passed only after abandoning that
checker path and constructing the terminal certificate locally. Existing prose
listed missing fields, but did not encode that the nested object was a reusable
request and belonged at the root. This is the bounded target for PR2; reasoning
log write errors and strategy choices are out of scope.

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
