# Integration test domains

Integration tests are grouped by the semantic owner of the behavior under
test. The directory selects ownership; pytest markers describe runtime traits
only.

| Directory | Owned behavior |
| --- | --- |
| `agent` | Agent benchmark and evaluation surfaces |
| `domains` | Cross-cutting mathematical domain bundles |
| `graph` | Graph capabilities and graph verification workflows |
| `infrastructure` | Kernel services, plugins, storage, MCP, and workspaces |
| `lean` | Lean-backed capabilities and proof editing |
| `matrix` | Matrix, linear-system, and polytope capabilities |
| `polynomial` | Polynomial maps, systems, and exact polynomial operations |
| `sat_smt` | SAT/SMT solvers, artifacts, proofs, and checkers |
| `workflow` | Claims, experiments, search, shrinking, and verification flows |

Use `make test-integration TESTS=tests/integration/<domain>` to run one owner.
