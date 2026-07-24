# Jacobian

Jacobian is a verifier-centric MCP toolbench for agents working on bounded,
executable mathematics.

It gives agents and researchers executable tools with which to propose
candidates, search large spaces, receive structured counter-witnesses, repair
claims, and replay exact certificates. The kernel is not a
`solve_conjecture` endpoint and does not treat model output or solver status as
mathematical truth.

The public kernel is domain-agnostic. Graphs, matrices, finite algebra,
optimization problems, numerical claims, and formal proof goals acquire their
mathematical meaning through plugins. Generality here means that those plugins
share the same artifact, evaluation, witness, shrinking, provenance, and
verification substrate—not that an informal conjecture requires no
formalization or domain implementation.

The central invariant is:

> Search and evaluation may be wrong. A result becomes verified only when an
> operator-authorized checker accepts evidence bound to the exact claim,
> semantics, candidate, and checker version.

## Get started

Jacobian uses Python 3.12 and `uv`. Initialize the locked development
environment and a local state directory:

```sh
uv sync --dev
uv run jacobian --state-dir .jacobian init
```

Then follow
[Find and verify a counterexample](docs/tutorials/first-verified-result.md)
for a complete first experiment. Run `uv run jacobian --help` to inspect the
CLI or `uv run jacobian-mcp` to start the MCP adapter.

## Roadmap

| Milestone | Theme | Primary outcome |
| --- | --- | --- |
| Current release | Verification and bounded discovery | v0.2 alpha stores, evaluates, attacks, shrinks, independently verifies, enumerates structures, verifies representation changes, and computes exact separators |
| M3 | Scalable search | Provisional implementation runs typed search strategies through one resumable experiment loop |
| M4 | Conjecture workflows | Provisional implementation repairs, generates, falsifies, and parametrically generalizes conjectures |
| M5 | Research corpus integration | Retrieve prior solutions, failures, witnesses, and certificates through an optional provider |
| Stability target | Stable research platform | Publish a v1.0 API with formal-checking and collaboration support |

The roadmap is tool-first: search and conjecture workflows remain useful
without a shared corpus service. Jacobian records its own experiments for
replay and lineage; corpus-scale retrieval is an optional integration that
cannot promote evidence or authorize checkers.

The only public release contract is v0.2 alpha (`0.2.0a0`). It includes the
verification kernel and bounded discovery. The repository also contains
provisional M3 and M4 implementations so their contracts can be exercised
before a later release is declared. Those APIs and artifacts are not part of
v0.2 conformance and remain free to change.

## Design and documentation

Jacobian is pre-stable, so the architecture, trust boundaries, and milestone
gates are part of the working project record. Start with:

- [Architecture](docs/explanation/architecture.md) for the system shape and
  verification boundary.
- [Roadmap](docs/explanation/roadmap.md) for active milestone scope and exit
  gates.
- [Architecture decision log](docs/explanation/adr/index.md) for accepted
  cross-cutting decisions and their release scope.
- [Threat model](docs/explanation/threat-model.md) for protected properties,
  trust assumptions, and explicit exclusions.
- [Durable search runtime](docs/explanation/search-runtime.md) for the
  provisional M3 ownership, persistence, and recovery model.

Release contracts and engineering evidence are:

- [Tool surface](docs/reference/tools.md)
- [v0.2 specification](docs/reference/specifications/v0.2.md) and
  [conformance gate](docs/reference/conformance-v0.2.md)
- [M3](docs/reference/milestones/m3-scalable-search.md) and
  [M4](docs/reference/milestones/m4-conjecture-workflows.md) provisional
  contracts
- [Testing strategy](docs/reference/testing-strategy.md),
  [scenario catalog](docs/reference/math-scenarios.md), and
  [performance benchmark protocol](docs/reference/performance-benchmarks.md)
- [Plugin conformance contract](docs/reference/plugin-conformance.md)

The [documentation home](docs/index.md) provides the complete catalog,
organized into tutorials, how-to guides, reference, and explanation. Read
[CONTRIBUTING.md](CONTRIBUTING.md) for development setup, verification rules,
documentation placement, and pull-request expectations.

## Current status

v0.2 alpha is implemented as a local Python package, CLI, and MCP adapter. It
offers eight verification tools alongside bounded enumeration,
implementation-bound canonicalization, independently verified representation
changes, persistent experiment resources, and exact finite-polytope evidence.
Bundled reference domains cover graph paths and bipartiteness, exact integer
matrices, and bounded Erdős-Straus decomposition tables. A verified
Erdős-Straus table establishes only its exact finite interval, never the open
unbounded conjecture.

The provisional M3/M4 code adds sealed plugin snapshots, a strategy-neutral
`search.run` service, pause and resume from immutable checkpoints, append-only
lifecycle events, conjecture transformations, and verified parameter-region
promotion. The scheduler accepts one strategy worker. Plugin calls run in
bounded child processes, but the search coordinator and durable state owner
remain local to one Jacobian process.

Use one active Jacobian process per state directory. Restarting that process
reconstructs interrupted searches as paused or cancelled from durable state;
it does not provide a multi-process lease or distributed queue. All public
contracts and artifact formats remain pre-stable.

Development commands and test-selection guidance live in
[CONTRIBUTING.md](CONTRIBUTING.md) and the
[testing strategy](docs/reference/testing-strategy.md).

The MCP adapter is pinned to the official Python SDK `2.0.0b2`. It remains
isolated from the mathematical kernel because that SDK release is a beta.
Exact finite-polytope generation uses Z3 rational constraints. Z3 output is
always unverified until the separate `Fraction`-based checker accepts the
bound witness or certificate.

### Local Codex

The repository includes a trusted-project Codex profile at
`.codex/config.toml`. Run Codex from the repository root and inspect
`jacobian_local` with `/mcp`; the profile starts `uv run jacobian-mcp` over
STDIO with the compact `verification` tool profile and stores durable local
state under the ignored `.jacobian/` directory. The profile projects eight
verification tools from the canonical registry and omits redundant MCP output
schemas. Domain resources expose compact claim contracts instead of repeating
the canonical stored schemas, and composite workflows return a concise stage
projection while leaving all durable artifacts unchanged. Start
`uv run jacobian-mcp --tool-profile full` when the research, transformation,
and experiment tools or complete wire results are needed.

This profile is local development configuration. It does not expose an HTTP
endpoint or provide remote authentication, tenant isolation, or hosted-service
authorization.

The public known-answer agent pilot launches a real Codex CLI against this
profile and validates the resulting durable verification records rather than
trusting the model's summary:

```sh
uv run python benchmarks/agent_mcp.py
```

Raw transcripts, isolated Jacobian state, reports, structured agent feedback,
and scores are written to the ignored `benchmarks/results/` directory.

### Lean certificates

`lean.verify` binds an exact Lean proposition and proof body into immutable
claim, candidate, and certificate artifacts, then invokes the ordinary
authorized `certificate.verify` boundary. Both bundled environments pin Lean
`4.31.0` commit `68218e876d2a38b1985b8590fff244a83c321783` and run with
`--trust=0`:

- `CORE` permits no import or axiom and is suitable for self-contained
  propositions such as elementary induction.
- `MATHLIB` generates exactly `import Mathlib`, pins mathlib commit
  `fabf563a7c95a166b8d7b6efca11c8b4dc9d911f`, and permits only the declared
  standard trust base `Classical.choice`, `Quot.sound`, and `propext`. Its
  operator-installed checker profile has a 75-second cold-start ceiling;
  normal checkers retain the 30-second default.

Prepare the pinned local runtime with:

```sh
cd lean
lake update
lake build
```

The checker rejects user-supplied imports, `sorry`, `admit`, `native_decide`,
unsafe declarations, and metaprogram execution. It verifies the requested
toolchain and mathlib commits and parses Lean's actual `#print axioms` result;
the result must be a subset of the selected environment's allowlist.

This is a trusted local Lean integration, not a broker sandbox. The mathlib
profile executes the repository's pinned Lake environment with host-local
runtime access. Arbitrary package ingestion and arbitrary imports are not
supported.

## Distribution

Jacobian is a Python package with an installed CLI and MCP server entry point.
The intended public distribution channel is PyPI once the alpha release is
ready. MCP is language-neutral and does not require an npm package; a separate
JavaScript package would be considered only if Jacobian later ships a
TypeScript client or adapter.

## Initial non-goals

- Natural-language-to-formal-mathematics automation
- A universal mathematical ontology
- A generic public `solver.solve` tool
- Arbitrary model-uploaded executable bundles
- Distributed search infrastructure
- A theorem prover or SAT/MIP solver implemented from scratch
- Treating floating-point scores, timeouts, or solver labels as proofs
