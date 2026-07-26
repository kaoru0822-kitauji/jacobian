# Jacobian

> A composable mathematical workbench for AI agents. Built for conjectures,
> counterexamples, and checkable evidence.

[![CI](https://github.com/morluto/jacobian/actions/workflows/ci.yml/badge.svg)](https://github.com/morluto/jacobian/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/jacobian)](https://pypi.org/project/jacobian/)
[![npm](https://img.shields.io/npm/v/jacobian)](https://www.npmjs.com/package/jacobian)
[![Python](https://img.shields.io/pypi/pyversions/jacobian)](https://pypi.org/project/jacobian/)
[![License: MIT](https://img.shields.io/github/license/morluto/jacobian)](LICENSE)

Jacobian is an MCP server, CLI, and Python library that gives AI agents
composable mathematical capabilities for high-level mathematics. Agents
retrieve premises, construct objects, compute invariants, search for
witnesses, and independently verify certificates: the operations an agent
needs to make trustworthy progress on conjectures and other problems where a
model's answer is not enough and checkable evidence is what counts.

## Why Jacobian?

Frontier models can now find counterexamples to open conjectures and propose
proofs that span pages of subtle algebra. The hard part is no longer only the
search. It is trust. A model's summary is not a proof, a solver's `SAT` label
is not a witness, and a high score is not a theorem. Jacobian is built for
that gap. It gives agents the operations to search, transform, and check
mathematical objects, and it keeps search, evaluation, and verification in
separate lanes so a claim becomes trusted only when an independent checker
accepts evidence bound to the exact statement.

This matters for the work that is hardest to verify by eye: a candidate
counterexample to a long-standing conjecture, a polynomial map that should or
should not be invertible, a finite witness that collapses a universal claim.
Jacobian exposes those as typed, inspectable artifacts: the witness, the
certificate, the rejected candidate, the stale attempt. A human reviewer or a
downstream agent can see what was tried, what passed, and what did not.

Each capability has one mathematically atomic, agent-visible outcome and
returns typed results with explicit scope, execution status, assurance, and
provenance. Existing mathematical software supplies the mathematics; capability
adapters expose it through a common contract. Jacobian supplies operations,
artifacts, execution policy, and trust boundaries, not a prescribed research
strategy. The public kernel is domain-agnostic: graphs, matrices, finite
algebra, optimization problems, and formal proof goals acquire their meaning
through plugins that share the same artifact, evaluation, witness, and
verification substrate.

> Search and evaluation may be wrong. A result becomes verified only when an
> operator-authorized checker accepts evidence bound to the exact claim,
> semantics, candidate, scope, certificate format, and checker version.

## Bundled capabilities

The kernel ships with capabilities across several mathematical domains. Each
one is a separately invocable operation with typed artifacts and explicit
assurance; agents compose them into research strategies.

- **Polynomial maps**: evaluate maps, compute Jacobians, search for and
  independently verify collisions (the witness type that refutes invertibility
  claims).
- **Polynomial systems and factorization**: verify exact solutions, factor
  polynomials, check identities.
- **Linear algebra**: compute determinants, rank, and kernels; find and
  verify exact rational `A x = b` solutions (optional `flint` extra).
- **SAT**: find models and UNSAT proofs with CaDiCaL, independently replay
  total assignments and DRAT proofs.
- **SMT**: find UNSAT proofs with cvc5, independently replay Alethe proofs
  with Carcara.
- **Graphs**: construct graphs, compute properties, enumerate paths, realize
  degree sequences, test isomorphism, search colorings.
- **Universal algebra**: evaluate finite magma laws, search for
  countermodels.
- **Polytopes**: convex combinations, linear separation.
- **Lean**: check proofs against pinned `CORE` and `MATHLIB` environments,
  discover declarations, retrieve premises, apply tactics.
- **Research memory**: durable, revisioned workspace for scratch entries,
  findings, attempts, and dependency-linked context.

See the [tool reference](docs/reference/tools.md) for the full contract per
capability and the [atomic capability portfolio](docs/contributing/atomic-capability-portfolio.md)
for the backend order and per-slice evaluation gates.

## Get started

Jacobian uses Python 3.12 and `uv`. Initialize the locked development
environment and a local state directory:

```sh
uv sync --dev
uv run jacobian --state-dir .jacobian init
```

### A first verified result

Find a graph with an incomplete path list, evaluate the claim, find an omitted
path, and verify it with an independent checker. The full script is in
[Find and verify a counterexample](docs/tutorials/first-verified-result.md);
the core sequence is:

```python
# Evaluate whether the proposed path list is complete.
evaluation = await tool(client, "capability.invoke", {
    "capability_id": "evaluate.batch",
    "mode": "EXPLORE",
    "payload": {"claim_uri": claim_uri, "candidate_uris": [candidate_uri], ...},
})
# evaluation: FALSE HEURISTIC  <- heuristic evidence, not yet verified

# Find a witness: an omitted path that defeats the candidate.
found = await tool(client, "capability.invoke", {
    "capability_id": "witness.find",
    "mode": "EXPLORE",
    "payload": {"claim_uri": claim_uri, "candidate_uri": candidate_uri, ...},
})

# Independently verify the witness with an authorized checker.
verified = await tool(client, "capability.invoke", {
    "capability_id": "witness.verify",
    "mode": "VERIFY",
    "payload": {"witness_uri": found["output"]["witness_uri"], ...},
})
# verification: FALSE VERIFIED  <- now a trusted conclusion
```

The gap between `FALSE HEURISTIC` and `FALSE VERIFIED` is the whole point:
search produces evidence, an independent checker produces trust.

Run `uv run jacobian --help` to inspect the CLI or `uv run jacobian-mcp` to
start the MCP adapter.

<details>
<summary><strong>macOS and Z3</strong></summary>

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

</details>

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
- [Durable search runtime](docs/explanation/search-runtime.md) for ownership,
  persistence, and recovery decisions.

Release contracts and engineering evidence are:

- [Tool surface](docs/reference/tools.md)
- [Provider runtime contract](docs/reference/provider-runtime.md) for
  availability, exact backend identity, install tiers, and local measurement.
- [SAT artifact contracts](docs/reference/sat-artifacts.md) for canonical CNF,
  raw model and proof identity, and independently checked total assignments.
- [SMT Alethe artifact contracts](docs/reference/smt-artifacts.md) for the
  pinned quantifier-free cvc5 producer and strict Carcara verification profile.
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
adapter registry and trust-labeled artifacts. See the
[Bundled capabilities](#bundled-capabilities) section above for the operation
portfolio, and the [tool reference](docs/reference/tools.md) for per-capability
contracts.

Some capabilities depend on optional backends that are not installed by
default: CaDiCaL for SAT model and UNSAT proof finding, cvc5 for SMT UNSAT
proof finding, and the `flint` extra for exact rational linear solutions.
Solver output always remains unverified until a separate, independent checker
accepts the bound witness or certificate. See the
[SAT artifact contracts](docs/reference/sat-artifacts.md),
[SMT artifact contracts](docs/reference/smt-artifacts.md), and
[exact rational solution contract](docs/reference/linear-rational-solutions.md)
for the verification boundaries.

Three direct operational tools, `workspace.open`, `workspace.write`, and
`workspace.query`, provide durable, revisioned paper-like working state outside
the mathematical capability and assurance model. Scratch entries, findings,
attempts, focus, and append-only lifecycle marks remain agent-authored and
`UNVERIFIED`. Explicit dependency links support bounded context retrieval and
derived stale warnings without promoting a claim.

All public capability contracts and artifact formats remain pre-stable unless
a release specification explicitly says otherwise. Development commands and
test-selection guidance live in [CONTRIBUTING.md](CONTRIBUTING.md) and the
[testing strategy](docs/reference/testing-strategy.md).

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
Model-in-the-loop evaluations are local, optional, and never part of
`make test-fast`, `make test`, `make validate-full`, or CI. Preview a selected
paired evaluation without executing a model:

```sh
make agent-eval EVAL_ARGS="--case ERDOS-STRAUS-AB-001"
```

After reviewing its case, condition, timeout, and model-run totals, dispatch it
manually with an explicit process budget:

```sh
make agent-eval EVAL_ARGS="--case ERDOS-STRAUS-AB-001 --execute --max-model-runs 2"
```

### Lean certificates

The `lean.check` capability binds an exact proposition and proof body to its
result and uses a pinned Lean environment. The bundled `CORE` and `MATHLIB`
environments pin Lean, their imports, and their allowed trust bases;
model-supplied imports and packages are rejected.

With bundled references enabled, `lean.proof_state.apply_tactic` and
`lean.retrieve.premises` expose one-step proof-state interaction and bounded
Mathlib `exact?` suggestions through the pinned upstream Lean REPL. They are
exploration aids only; their output cannot become `VERIFIED` without a
successful exact `lean.check`.

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
