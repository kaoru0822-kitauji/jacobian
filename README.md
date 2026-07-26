# Jacobian

Jacobian is an MCP server, CLI, and Python library that exposes composable
mathematical capabilities to AI agents. Its goal is to help agents and human
researchers make trustworthy progress on conjectures and other problems that
benefit from executable search and checkable evidence.

Capabilities have mathematically atomic, agent-visible outcomes: retrieve
premises, construct an object, compute an invariant, transform a claim, search
for a witness, or check a certificate. Agents compose these operations into
research strategies. Optional workflows preserve their intermediate artifacts,
and independent checkers verify exact claims and evidence.

Each operation returns typed, inspectable results with explicit relationships,
scope, execution status, assurance, and provenance. Existing mathematical
software and domain plugins supply the mathematics; capability adapters expose
it through a common contract. Jacobian supplies operations, artifacts,
execution policy, and trust boundaries—not a prescribed research strategy.

The public kernel is domain-agnostic. Graphs, matrices, finite algebra,
optimization problems, numerical claims, and formal proof goals acquire their
mathematical meaning through plugins. Those plugins share the same artifact,
evaluation, witness, shrinking, provenance, and verification substrate.
Exploration may use models, heuristics, solvers, and external mathematical
systems. Evidence that needs to become a trusted conclusion must enter a
separate assurance lane:

> Search and evaluation may be wrong. A result becomes verified only when an
> operator-authorized checker accepts evidence bound to the exact claim,
> semantics, candidate, scope, certificate format, and checker version.

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

## Direction

Jacobian develops a broad portfolio of mathematical capabilities in parallel.
Search, construction, transformation, retrieval, computation, and formal
proof are not sequential milestones. Experimental adapters may be exposed and
changed quickly; held-out evaluations guide discovery, routing, defaults,
consolidation, and retirement.

The active [product goals](docs/explanation/goals.md) are to expand
mathematical capability, improve agent discovery and composition, increase
independent verification coverage, evaluate portfolios on real mathematical
work, preserve transparent intermediate evidence, and keep the public MCP
surface small.

Release specifications describe supported behavior at a point in time. They
do not prescribe research order or gate experimental capabilities.

## Design and documentation

Jacobian is pre-stable, so its architecture, trust boundaries, and active
goals are part of the working project record. Start with:

- [Architecture](docs/explanation/architecture.md) for the system shape and
  verification boundary.
- [Product model](docs/explanation/product-blueprint.md) for the primitive
  contract, ownership boundaries, agent-facing API, and evaluation direction.
- [Product goals](docs/explanation/goals.md) for the rolling priorities and
  planning model.
- [Atomic capability portfolio](docs/contributing/atomic-capability-portfolio.md)
  for the formal-first backend order, installation tradeoffs, and per-slice
  evaluation gates.
- [Architecture decision log](docs/explanation/adr/index.md) for accepted
  cross-cutting decisions and their release scope.
- [Epistemic workspace ADR](docs/explanation/adr/0005-direct-epistemic-workspaces.md)
  for the separation between durable working state and mathematical assurance.
- [Threat model](docs/explanation/threat-model.md) for protected properties,
  trust assumptions, and explicit exclusions.
- [Durable search runtime](docs/explanation/search-runtime.md) for ownership,
  persistence, and recovery decisions.

Release contracts and engineering evidence are:

- [Tool surface](docs/reference/tools.md)
- [Provider runtime contract](docs/reference/provider-runtime.md) for
  availability, exact backend identity, install tiers, and local measurement.
- [SAT artifact contracts](docs/reference/sat-artifacts.md) for canonical CNF,
  total assignment, and raw proof identity before solver or checker
  installation.
- [v0.2 specification](docs/reference/specifications/v0.2.md) and
  [conformance gate](docs/reference/conformance-v0.2.md)
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

Jacobian is implemented as a Python package, CLI, and local or remote MCP
adapter. The agent-facing MCP surface uses `capability.describe` for exact
contracts and `capability.invoke` for execution, backed by an extensible
adapter registry and trust-labeled artifacts. Bundled capabilities cover graph
construction and properties, exact rational polynomial maps, finite magma law
evaluation and countermodel search, reference-domain exploration and
verification, Lean checking, and local research-memory search.

The base kernel also registers canonical CNF, total assignment, and raw DRAT
proof artifact contracts. They do not add SAT capabilities or mathematical
assurance; solver and independent-checker slices remain separate.

Three direct operational tools—`workspace.open`, `workspace.write`, and
`workspace.query`—provide durable, revisioned paper-like working state outside
the mathematical capability and assurance model. Scratch entries, findings,
attempts, focus, and append-only lifecycle marks remain agent-authored and
`UNVERIFIED`. Explicit dependency links support bounded context retrieval and
derived stale warnings without promoting a claim.

All public capability contracts and artifact formats remain pre-stable unless
a release specification explicitly says otherwise.

Development commands and test-selection guidance live in
[CONTRIBUTING.md](CONTRIBUTING.md) and the
[testing strategy](docs/reference/testing-strategy.md).

The MCP adapter remains isolated from the mathematical kernel. Exact
finite-polytope generation uses Z3 rational constraints, but Z3 output remains
unverified until the separate `Fraction`-based checker accepts the bound
witness or certificate.

### MCP clients

Configure a client against `jacobian-mcp` or the remote endpoint described
below. The server advertises `capability.describe`, `capability.invoke`, and
the three direct `workspace.*` tools. Describe an unfamiliar mathematical
capability before invoking it; direct workspace tools publish their own
schemas. `capability://catalog` remains a resource-level catalog for clients
that support MCP resources.

For ChatGPT and other remote clients, the server supports Streamable HTTP and
SSE, bearer-token authentication, and subject-bound tenant state. Follow
[Deploy the remote MCP server](docs/how-to/deploy-remote-mcp.md). Static tokens
are an initial controlled-deployment mechanism, not a full hosted identity
platform.

The public known-answer agent pilot validates durable verification records
rather than trusting the model's summary. It requires an operator-configured
Jacobian MCP connector:

```sh
uv run python benchmarks/agent_mcp.py
```

Raw transcripts, isolated Jacobian state, reports, structured agent feedback,
and scores are written to the ignored `benchmarks/results/` directory.
Use `uv run python benchmarks/agent_ab.py` for paired no-Jacobian versus
capability-enabled runs once the A/B cases are selected.

### Lean certificates

The `lean.check` capability binds an exact proposition and proof body to its
result and uses a pinned Lean environment. The bundled `CORE` and `MATHLIB`
environments pin Lean, their imports, and their allowed trust bases;
model-supplied imports and packages are rejected.

Prepare the pinned local runtime with:

```sh
elan toolchain install leanprover/lean4:v4.31.0
cd lean
lake update
lake build
```

The operation and trust boundary are documented under
[`lean.check`](docs/reference/tools.md). Read-only
[Lean declaration discovery](docs/reference/lean-declaration-discovery.md)
can retrieve and inspect premises before completed source crosses that checker
boundary; the [guided reproduction](docs/tutorials/lean-declaration-discovery.md)
shows the composition. This is a trusted local integration, not a broker
sandbox; the pinned Lake environment still has host-local runtime access.

## Distribution

Jacobian ships through both PyPI and npm. The Python distribution provides the
library, CLI, and MCP server. The npm package is the supported Node launcher
and MCP client installer: it bootstraps the Python distribution, registers
Jacobian with supported MCP clients, verifies the server handshake, and
forwards commands to the Python CLI.

The npm package does not duplicate the mathematical kernel or imply a separate
JavaScript API. Both distributions expose the same Jacobian implementation.

## Initial non-goals

- A universal natural-language-to-formal-mathematics translator in the kernel
- A universal mathematical ontology
- One opaque generic solver that hides backend semantics
- Arbitrary model-uploaded executable bundles
- Distributed search infrastructure
- A theorem prover or SAT/MIP solver implemented from scratch
- Treating floating-point scores, timeouts, or solver labels as proofs
