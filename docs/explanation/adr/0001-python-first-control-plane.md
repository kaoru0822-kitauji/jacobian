# ADR 0001: Use a Python-first control plane

[Documentation home](../../index.md) · [Decision log](index.md)

- Status: Accepted for v0.2
- Date: 2026-07-23

## Decision

Use Python 3.12 for Jacobian's orchestration layer, schemas, plugin interfaces,
artifact store, local search loops, CLI, initial exact replay checkers, and MCP
adapter.

Use established native or external systems for specialized computation. Python
is the control plane, not a replacement SAT, SMT, LP, MIP, graph
canonicalization, or proof engine.

## Why Python

The decision is primarily driven by integration and iteration speed:

- The official MCP SDK has a Python implementation.
- Pydantic provides typed runtime validation and JSON Schema generation.
- Mathematical and optimization systems commonly provide maintained Python
  bindings.
- NetworkX, Hypothesis, and the standard exact `Fraction` type are sufficient
  for initial bounded reference plugins.
- Python makes it inexpensive to write domain plugins and compose existing
  solvers while their public semantics remain defined by language-neutral
  schemas.

This is not a claim that Python is the best language for every checker or
compute kernel.

## What Python owns

- Artifact and result schemas
- Canonicalization orchestration and hashing
- Artifact and run storage
- Problem capability interfaces
- Evaluation, witness-search, and shrinking orchestration
- Experiment archives and lineage
- CLI and MCP adapter
- Initial small reference checkers

## What Python does not reimplement

- SAT, SMT, or pseudo-Boolean solving
- LP or MIP solving
- Graph canonical labeling
- BDD or ZDD engines
- Formal proof kernels
- Hardened operating-system sandboxing

These systems remain typed backends:

```text
Python runtime
    ├── Z3 / cvc5 / PySAT / OR-Tools
    ├── HiGHS / SCIP / SoPlex
    ├── nauty / Graphillion
    ├── pycddlib / polymake / Normaliz
    └── Lean 4
```

## v0.2 libraries

| Capability | Choice |
| --- | --- |
| Runtime | Python 3.12 |
| Environment and lockfile | uv |
| Data validation | Pydantic v2 |
| Wire contracts | Versioned JSON Schema |
| Exact arithmetic | `int` and `fractions.Fraction` |
| Hashing | `hashlib.sha256` |
| Run metadata | SQLite in WAL mode |
| Blob storage | Atomic digest-keyed filesystem |
| Search-side graph handling | NetworkX |
| Exact finite-polytope generation | Z3 |
| CLI | Typer |
| Tests | pytest, Hypothesis, and `jsonschema` |
| Performance benchmarks | pyperf |
| MCP | Official Python MCP SDK `2.0.0` |
| Local execution | Sequential orchestration with bounded child processes |

Pydantic validates data but does not define canonical cross-language bytes.
Jacobian therefore owns a versioned canonical artifact encoding and forbids
JSON floating-point values in exact mathematical objects.

An independent graph-domain checker should use a small standard-library graph
traversal instead of importing its search plugin's NetworkX routines.

Z3 is a required v0.2 runtime dependency for exact rational finite-polytope
membership and separation. It generates candidate weights and separating
certificates, but it does not authorize their mathematical conclusions. The
independent checker replays those artifacts with `fractions.Fraction` and does
not import Z3.

The pre-stable control plane pins the released MCP v2 packages exactly:

```toml
mcp = "==2.0.0"
mcp-types = "==2.0.0"
```

The exact pins prevent an unreviewed SDK drift. The MCP adapter is isolated
under `adapters/mcp` so protocol changes do not affect mathematical schemas or
verification code.

## Specialized backends

### Required in v0.2

- Z3 for exact rational finite-polytope membership and separation

### Planned optional backends

- nauty/gtools for graph canonicalization and nonisomorphic generation
- pycddlib through `cdd.gmp` for exact rational polyhedra
- HiGHS for exploratory LP/MIP
- SoPlex for exact rational LP
- `gmpy2.mpq` if `Fraction` becomes a measured bottleneck

Candidate backends to evaluate when a capability needs them:

- PySAT for SAT, MaxSAT, and MUS/MCS workflows
- cvc5 for SMT and SyGuS
- OR-Tools CP-SAT for bounded integer combinatorics
- SCIP/PySCIPOpt for MIP and branch-cut-price
- Graphillion or other BDD/ZDD systems for symbolic graph families
- Lean 4 and mathlib for formal checking
- PostgreSQL and S3-compatible storage if distributed execution justifies them

Jacobian does not plan to provide a security sandbox. Plugins and checkers are
operator-installed local code. A remote or multi-tenant deployment that accepts
untrusted executable uploads would need its own isolation layer outside the
research runtime.

Optional backends are installed in dependency groups. They do not become
dependencies of the trusted checker API merely because a search plugin uses
them.

## Alternatives considered

### Rust-first

Rust would be attractive for hardened parsers, checkers, and high-throughput
services. It would make the initial solver and research-library integration
slower. Rust remains an option for individual mature checker implementations.

### TypeScript-first

TypeScript has strong MCP and service tooling but a substantially weaker
scientific-computing and mathematical-solver ecosystem for this project.

### C++-first

C++ would align with many native engines but would increase iteration and
plugin-development cost without improving the initial trust model.

### Polyglot services from the start

This would maximize implementation independence but create deployment,
serialization, and compatibility work before the verification loop is proven.

## Consequences

- Python-specific implementation types must not leak into artifact schemas.
- Performance-critical paths are measured before being moved to native code.
- Native solver results are treated as untrusted evidence until replayed.
- Checker isolation is enforced by package dependencies and process boundaries,
  not merely by choosing another language.
- A future non-Python implementation can interoperate through the versioned
  schemas and certificate formats.
