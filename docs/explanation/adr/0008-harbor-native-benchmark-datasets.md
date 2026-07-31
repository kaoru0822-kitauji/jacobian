# Harbor-native benchmark datasets

Status: Accepted, pre-stable

## Context

ADR 0007 organized `benchmarks/` by artifact class. That made the distinction
between workflow observations, public reproductions, research diagnostics,
performance measurements, provider spikes, and examples visible, but only one
class was executable as Harbor tasks. The remaining classes used unrelated
JSON ledgers and Python entry points. The frozen `regression-v1` name also
suggested a product regression gate even though its model runs observe fixed
agent workflows and do not establish causal performance.

Harbor local dataset loading inspects only immediate child task directories.
The mathematical subject taxonomy we want is nested by domain and field, so a
nested `tasks/` directory cannot itself be passed to Harbor as a local dataset.

## Decision

Every executable benchmark case is owned by one self-contained Harbor task
under `benchmarks/datasets/<dataset>/tasks/<domain>/<field>/<task>/`. The task
layout follows the Terminal-Bench Science review pattern: agent-visible
instructions and environment, Oracle-only solution material, verifier-only
tests, and a maintainer README. Jacobian retains its stricter provenance,
assurance, artifact-integrity, and fail-closed verification rules.

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
Each dataset's `suite.toml` is the source of truth for local task membership
and nested paths. `dataset.toml` is generated from the validated suite and
Harbor's task checksum implementation; manual digest edits are drift. Job
templates are rendered into temporary Harbor configs containing one explicit
`tasks: [{"path": ...}]` entry per suite task.

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

This ADR supersedes only the benchmark-layout decision in ADR 0007. ADR 0007's
package layout and no-shim package decisions remain accepted.
