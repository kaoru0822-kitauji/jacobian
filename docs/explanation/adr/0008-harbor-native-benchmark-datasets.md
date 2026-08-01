# Harbor-native benchmark datasets

Status: Accepted, pre-stable

## Context

The benchmark tree distinguishes workflow observations, public reproductions,
research diagnostics, performance measurements, provider spikes, and examples,
but only one class is executable as Harbor tasks. The frozen `regression-v1`
name also suggested a product regression gate even though its model runs
observe fixed agent workflows and do not establish causal performance.
Non-runnable research plans and discovery handoffs need a separate home from
executable benchmark cases.

Harbor local dataset loading expects standalone task directories. The
mathematical subject taxonomy is useful metadata, but it must not become a
second identity or force a task to be copied for another dataset.

## Decision

Every executable benchmark case is one self-contained Harbor task under
`benchmarks/tasks/<task-id>/`. Dataset member fragments select canonical tasks
without copying them. The task layout follows the Terminal-Bench Science review pattern: agent-visible
instructions and environment, Oracle-only solution material, verifier-only
tests, and a maintainer README. Jacobian retains its stricter provenance,
assurance, artifact-integrity, and fail-closed verification rules.

The repository has three explicit ownership boundaries. `benchmarks/datasets/`
contains executable Harbor cases and their dataset manifests.
`benchmarks/tooling/` contains reusable Harbor infrastructure and does not own
a second task list. `research/evaluations/` contains non-runnable evaluation
plans, discovery handoffs, and reports. Research records may reference
canonical dataset paths, but they are not Harbor datasets, are not injected
into agent containers, and must not be treated as performance evidence without
a separately frozen held-out evaluation.

Six datasets keep different claims separate:

- `jacobian/agent-workflow-v1`;
- `jacobian/public-reproductions-v1`;
- `jacobian/research-diagnostics-v1`;
- `jacobian/performance-v1`;
- `jacobian/provider-feasibility-v1`; and
- `jacobian/examples-v1`.

Uniform task structure does not make their rewards comparable. Each suite
declares its claim class, answer visibility, execution profile, and assurance
ceiling.

`registry.toml` discovers datasets but does not duplicate task membership.
Each dataset's `members/*.toml` fragments are the source of truth for dataset
membership and policy. `dataset.toml` is generated from the validated members and
Harbor's task checksum implementation; manual digest edits are drift. Job
templates are rendered into temporary Harbor configs containing one explicit
`tasks: [{"path": ...}]` entry per selected canonical task.

The canonical verifier protocol support lives in repository-owned Harbor
tooling. Each task receives a byte-identical ordinary file because task and
verifier images must be self-contained. Symlinks and compatibility paths are
not permitted.

`regression-v1` is renamed to `agent-workflow-v1`. The old benchmark-class
directories, direct runners, path aliases, and duplicate fixture homes are
removed in the same migration.

## Visibility and assurance

`instruction.md` and `environment/` are agent-visible. `solution/` is
Oracle-only, `tests/` is verifier-only, and task `README.md` is maintainer
context that is not injected into trials. Suite metadata and jobs remain
outside task containers.

Every submission uses the common fail-closed envelope. A task may accept
`claimed_assurance = "VERIFIED"` only when an operator-authorized independent
checker binds the exact claim, semantics, candidate, scope, evidence, and
checker identity. Knowing an Oracle answer does not raise the ceiling above
`COMPUTED`.

## Consequences

Benchmark discovery, manifest generation, job rendering, verifier-support
synchronization, and integrity checks share one repository-owned suite
boundary. Nested mathematical taxonomy no longer depends on Harbor's local
directory recursion.

Adding a case costs more than appending a JSON row: it requires an executable
environment, an Oracle path, an independent verifier, explicit provenance,
and a suite entry. In return, every retained case has one publishable identity,
one content digest, and inspectable visibility boundaries.

This ADR owns the benchmark dataset boundary. Changes to that boundary require
a new ADR rather than a silent rewrite.
