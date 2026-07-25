# Jacobian

Jacobian provides composable mathematical tools for AI agents investigating
conjectures and other mathematically specified problems. Agents use these tools
to search for counterexamples, construct and compare mathematical objects,
compute invariants, decompose proof goals, retrieve premises, develop candidate
proofs, and replay certificates.

Each tool performs a bounded, observable operation and returns typed,
inspectable artifacts with explicit relationships, scope, execution status,
assurance, and provenance. Existing mathematical software and domain plugins
supply mathematical operations; capability adapters expose them through a
common contract. Jacobian provides the composition, artifact, execution, and
assurance layer.

Jacobian's long-term goal is to help agents and human researchers make genuine,
trustworthy progress on open conjectures and other problems that benefit from
executable search and checkable evidence.

The public kernel is domain-agnostic. Graphs, matrices, finite algebra,
optimization problems, numerical claims, and formal proof goals acquire their
mathematical meaning through plugins. Those plugins share the same artifact,
evaluation, witness, shrinking, provenance, and verification substrate.
Exploration may use models, heuristics, solvers, and external mathematical
systems. Evidence that needs to become a trusted conclusion must enter a
separate assurance lane:

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

### macOS and Z3

The locked environment currently uses `z3-solver` 4.16.0.0. Its upstream
macOS wheels are built for macOS 15 or newer on both Apple silicon and Intel.
On an older macOS release, `uv` cannot use those wheels and falls back to
building Z3 from its source distribution.

That source build uses CMake, `make`, and a C++20 compiler. Install the Xcode
Command Line Tools, which provide Apple Clang and `make`, and make sure CMake
is available before retrying `uv sync --dev`. These commands identify the
platform and missing build tools without changing the environment:

```sh
sw_vers -productVersion
uname -m
xcode-select -p
clang++ --version
cmake --version
make --version
```

If `uv sync --dev` reports that it is building `z3-solver` and then fails,
include that command output and the diagnostics above in a bug report. See the
[`z3-solver` 4.16.0.0 files on PyPI](https://pypi.org/project/z3-solver/4.16.0.0/#files)
for the upstream wheel compatibility tags.

Then follow
[Find and verify a counterexample](docs/tutorials/first-verified-result.md)
for a complete first experiment. Run `uv run jacobian --help` to inspect the
CLI or `uv run jacobian-mcp` to start the MCP adapter.

## Roadmap

| Milestone | Theme | Primary outcome |
| --- | --- | --- |
| Current release | Verification and bounded discovery | v0.2 alpha stores, evaluates, attacks, shrinks, independently verifies, enumerates structures, verifies representation changes, and computes exact separators |
| Current product track | Mathematical tools for AI agents | One extensible model-facing API exposes typed operations for exploration, composition, replay, and optional verification |
| M3 | Scalable search | Provisional implementation runs typed search strategies through one resumable experiment loop |
| M4 | Claim transformation | Decompose broad claim-development workflows into typed generation, repair, ranking, falsification, and parameter-analysis operations |
| M5 | Federated research corpus | Extend the implemented local episode database with optional cross-project providers, review, retraction, and temporal retrieval |
| Stability target | Stable research platform | Publish a v1.0 API with formal-checking and collaboration support |

The roadmap is tool-first and artifact-first. Agent workflows may compose
versioned capabilities, and completed capability episodes are recorded and
searchable without a shared service. Corpus-scale retrieval is optional and
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
- [Product model](docs/explanation/product-blueprint.md) for the primitive
  contract, ownership boundaries, agent-facing API, and evaluation direction.
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
- [M3](docs/reference/milestones/m3-scalable-search.md),
  [M4](docs/reference/milestones/m4-conjecture-workflows.md), and
  [M5](docs/reference/milestones/m5-research-corpus.md) provisional contracts
- [v1.0 stability target](docs/reference/specifications/v1.0.md)
- [Testing strategy](docs/reference/testing-strategy.md),
  [scenario catalog](docs/reference/math-scenarios.md), and
  [performance benchmark protocol](docs/reference/performance-benchmarks.md)
- [Plugin conformance contract](docs/reference/plugin-conformance.md) and
  [agent evaluation protocol](docs/reference/agent-evaluations.md)

The [documentation home](docs/index.md) provides the complete catalog,
organized into tutorials, how-to guides, reference, and explanation. Read
[CONTRIBUTING.md](CONTRIBUTING.md) for development setup, verification rules,
documentation placement, and pull-request expectations.

## Current status

v0.2 alpha is implemented as a Python package, CLI, and local or remote MCP
adapter. The compact projection exposes `capability.describe` for discovery
and `capability.invoke` for execution, backed by an extensible adapter registry
and trust-labeled research memory. Bundled capabilities provide bounded Graph
Atlas construction, exact graph-property batches, reference-domain exploration
and verification, Lean checking, and local episode search.

The advanced profiles expose the lower-level operations documented in the
[tool reference](docs/reference/tools.md), including bounded enumeration,
independently checked representation changes, persistent experiments, and
exact finite-polytope evidence. Bundled reference domains cover graph paths and
bipartiteness, exact integer matrices, and bounded Erdős-Straus decomposition
tables. A verified Erdős-Straus table establishes only its exact finite
interval, never the open unbounded conjecture.

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

The MCP adapter remains isolated from the mathematical kernel. Exact
finite-polytope generation uses Z3 rational constraints, but Z3 output remains
unverified until the separate `Fraction`-based checker accepts the bound
witness or certificate.

### Local Codex

The repository includes a trusted-project Codex profile at
`.codex/config.toml`. Run Codex from the repository root and inspect
`jacobian_local` with `/mcp`; the profile starts `uv run jacobian-mcp` over
STDIO with the compact `capabilities` profile and stores durable local state
under the ignored `.jacobian/` directory. The profile advertises
`capability.describe` and `capability.invoke`. Describe an unfamiliar
capability before invoking it; reference domains include exact predicate and
candidate schemas plus executable examples. `capability://catalog` remains a
resource-level catalog for clients that support MCP resources. Start
`uv run jacobian-mcp --tool-profile full` when the research, transformation,
and experiment tools or complete wire results are needed.

For ChatGPT and other remote clients, the server supports Streamable HTTP and
SSE, bearer-token authentication, and subject-bound tenant state. Follow
[Deploy the remote MCP server](docs/how-to/deploy-remote-mcp.md). Static tokens
are an initial controlled-deployment mechanism, not a full hosted identity
platform.

The public known-answer agent pilot launches a real Codex CLI against this
profile and validates the resulting durable verification records rather than
trusting the model's summary:

```sh
uv run python benchmarks/agent_mcp.py
```

Raw transcripts, isolated Jacobian state, reports, structured agent feedback,
and scores are written to the ignored `benchmarks/results/` directory.
Use `uv run python benchmarks/agent_ab.py` for paired no-Jacobian versus
capability-enabled runs once the A/B cases are selected.

### Lean certificates

The `lean.check` capability uses the `lean.verify` compatibility workflow to
bind an exact proposition and proof body into immutable artifacts, then replay
them through the authorized `certificate.verify` boundary. The bundled `CORE`
and `MATHLIB` environments pin Lean, their imports, and their allowed trust
bases; model-supplied imports and packages are rejected.

Prepare the pinned local runtime with:

```sh
elan toolchain install leanprover/lean4:v4.31.0
cd lean
lake update
lake build
```

The operation and trust-boundary mapping are documented under
[`lean.check` and `lean.verify`](docs/reference/tools.md). This is a trusted
local integration, not a broker sandbox; the pinned Lake environment still has
host-local runtime access.

## Distribution

Jacobian is a Python package with an installed CLI and MCP server entry point.
The intended public distribution channel is PyPI once the alpha release is
ready. MCP is language-neutral and does not require an npm package; a separate
JavaScript package would be considered only if Jacobian later ships a
TypeScript client or adapter.

## Initial non-goals

- A universal natural-language-to-formal-mathematics translator in the kernel
- A universal mathematical ontology
- One opaque generic solver that hides backend semantics
- Arbitrary model-uploaded executable bundles
- Distributed search infrastructure
- A theorem prover or SAT/MIP solver implemented from scratch
- Treating floating-point scores, timeouts, or solver labels as proofs
