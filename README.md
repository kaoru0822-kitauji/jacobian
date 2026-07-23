# Jacobian

Jacobian is a verifier-centric research kernel for bounded, executable
mathematics.

It gives models and researchers a common environment in which they can propose
candidates, search large spaces, receive structured counter-witnesses, minimize
discoveries, and replay exact certificates. The kernel is not a
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

## Release sequence

| Release | Theme | Primary outcome |
| --- | --- | --- |
| v0.1 | Verification kernel | Store, evaluate, attack, shrink, and independently verify plugin-defined bounded candidates |
| v0.2 | Bounded discovery | Enumerate structures, verify representation changes, and compute exact separators |
| v0.3 | Scalable search | Run evolutionary, CEGIS, and tree search as resumable experiments |
| v0.4 | Research memory | Retrieve failures and certificates and suggest recurring abstractions |
| v0.5 | Conjecture development | Repair, generate, and parametrically generalize conjectures |
| v1.0 | Stable research platform | Publish a stable API with formal-checking and collaboration support |

v0.1 is the only normative implementation target. Later specifications are
provisional and may change in response to evidence from earlier releases.

## Documents

- [Architecture](docs/architecture.md)
- [Tool surface](docs/tools.md)
- [Roadmap and release gates](docs/roadmap.md)
- [Reference benchmarks](docs/benchmarks.md)
- [Mathematical scenario catalog](docs/math-scenarios.md)
- [Testing strategy and critical areas](docs/testing-strategy.md)
- [Performance benchmarks](docs/performance-benchmarks.md)
- [Model-in-the-loop evaluations](docs/agent-evaluations.md)
- [Threat model](docs/threat-model.md)
- [v0.1 conformance specification](docs/conformance-v0.1.md)
- [v0.1 specification](docs/specifications/v0.1.md)
- [v0.2 specification](docs/specifications/v0.2.md)
- [v0.3 specification](docs/specifications/v0.3.md)
- [v0.4 specification](docs/specifications/v0.4.md)
- [v0.5 specification](docs/specifications/v0.5.md)
- [v1.0 specification](docs/specifications/v1.0.md)
- [Why the control plane is Python-first](docs/adr/0001-python-first-control-plane.md)
- [Proposed implementation issues](docs/issues.md)

## Current status

v0.1 alpha is implemented as a local Python package, CLI, and MCP adapter. Its
seven-tool verification surface and artifact format remain pre-stable while
the conformance suite and reference domains mature.

```sh
uv sync --dev
uv run pytest
uv run ruff check .
uv run mypy
uv run jacobian --help
uv run jacobian-mcp
```

The MCP adapter is pinned to the official Python SDK `2.0.0b2`. It remains
isolated from the mathematical kernel because that SDK release is a beta.

## Initial non-goals

- Natural-language-to-formal-mathematics automation
- A universal mathematical ontology
- A generic public `solver.solve` tool
- Arbitrary model-uploaded executable bundles
- Distributed search infrastructure
- A theorem prover or SAT/MIP solver implemented from scratch
- Treating floating-point scores, timeouts, or solver labels as proofs
