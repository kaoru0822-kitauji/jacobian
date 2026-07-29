# ADR 0006: Isolate tests by semantic depth and resource ownership

[Documentation home](../../index.md) · [Decision log](index.md)

- Status: Accepted for the pre-stable test architecture
- Date: 2026-07-29

## Decision

Organize tests into six semantic tiers:

- `unit` for pure logic and models;
- `component` for one real service or adapter;
- `domain` for core services plus explicitly named domain bundles;
- `composition` for complete runtime, portfolio, authority, CLI, and lifecycle;
- `boundary` for persistence, recovery, subprocess, MCP, and optional providers;
- `e2e` for a small set of packaged user workflows.

Each test uses the lowest tier capable of proving its claim. Complete-runtime
construction is unavailable to unit, component, and domain tests. Domain tests
install literal `DomainBundle` values through the production installer; only
composition, explicit runtime/recovery boundaries, and end-to-end tests may
construct the complete built-in portfolio.

Directory ownership is authoritative. Execution markers remain only for
behavior that changes a lane: provider readiness, performance sampling,
scheduled property repetition, or destructive child-process containment.
A validated `tests/topology.toml` declares each lane's paths, worker topology,
timeout, environment, timing policy, and CI eligibility. A thin runner turns
one lane plus an optional pytest node ID into a pytest command. It does not
reimplement collection, filtering, retries, or fixture resolution.

## Rationale

The previous `integration` pool combined domain behavior, complete composition,
SQLite durability, subprocesses, MCP transports, providers, recovery, and
end-to-end workflows. One xdist scheduler and one timeout could not express
their incompatible CPU, memory, filesystem, process, and toolchain ownership.
Complete runtime construction also became a convenient service locator for
claims that needed only one domain bundle or service.

Pytest already provides hierarchical `conftest.py` visibility, scoped fixture
caching, yield teardown, exact node selection, and independent invocations.
Those primitives can express ownership directly. The repository therefore
keeps pytest as executor and Make as a command index instead of growing a
central runner with hard-coded exceptions.

The topology adopts two useful external patterns without copying their
accumulated complexity:

- uv-style per-test filesystem and environment ownership, exact-test commands,
  and explicit resource groups;
- PyTorch-style focused inclusion, timing-informed compatible shards, and
  clean-process or serial groups.

## Resource and fixture ownership

Root `tests/conftest.py` contains only cheap universal fixtures and collection
validation. Service, domain, complete-runtime, storage, process, MCP, and
provider fixtures live beneath their owning tier.

Mutable runtime, connection, registry, and workspace objects are function
scoped. A session-scoped template may contain only immutable state. Shared
templates are constructed in a temporary sibling and published by atomic
rename; an in-directory readiness marker never represents completeness. Every
test receives an isolated copy or reflink of the published template.

SQLite durability remains a boundary claim. WAL concurrency, synchronous
barriers, transaction recovery, and directory fsync behavior are tested in the
storage lane rather than paid by unrelated domain tests.

## Process and timeout policy

Separate pytest invocations are the primary resource boundary. Unit tests run
sequentially; component and domain lanes may use up to four workers;
composition, process, and MCP lanes use at most two; storage, Lean, and
end-to-end lanes are serial.

Timeouts contain deadlocks; they are not performance assertions. Native or
external operations that may ignore Python signal delivery run in a killable
child process. The parent owns the deadline and terminates the process group.
Correctness failures are not retried into passes.

## Planning and enforcement

The existing changed-path planner consumes the validated topology. Unknown
paths, deletes, renames, shared infrastructure, and ambiguous transitive
changes fail closed to owning lanes. Compatible domain tests may use
lane-local timing history; storage, composition, process, provider, and
end-to-end work is never mixed only to balance aggregate duration.

Architecture checks enforce:

- every test file belongs to exactly one lane;
- lower tiers cannot import or invoke complete-runtime construction;
- unit tests cannot access SQLite or process/provider boundaries;
- component and domain tests cannot install the built-in portfolio;
- provider implementation imports stay in provider boundaries or focused
  adapter components;
- root fixtures cannot acquire high-cost resources;
- configured paths and source-ownership rules resolve to tracked files.

Validation receipts remain bound to the exact git tree and working-tree digest.

## Consequences

- Test paths, fixtures, markers, and Make targets intentionally break during
  the pre-stable transition; no compatibility aliases or dual topology remain.
- Runtime and portfolio composition gain explicit production seams so tests do
  not maintain a second composition system.
- CI reports timings by resource lane and duplicates setup only when measured
  critical-span reduction justifies it.
- Startup benchmarks separate store bootstrap, core-service assembly,
  one-domain installation, complete portfolio materialization, attachment, and
  authorized-reference hydration.
- Performance gates begin from measured post-migration evidence. Correctness
  never depends on machine-local wall-clock assertions.
