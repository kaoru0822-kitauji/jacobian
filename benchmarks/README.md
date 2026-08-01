# Jacobian Harbor datasets

Every executable benchmark case is a self-contained Harbor task. The six
dataset identities below keep workflow observations, public reproductions,
research diagnostics, operational measurements, provider feasibility, and
examples from making incompatible claims look comparable.

`benchmarks/datasets/` is the home for executable Harbor cases. Reusable Harbor
infrastructure belongs under `benchmarks/tooling/`; non-runnable evaluation
plans and research handoffs belong under `research/evaluations/`.

| Dataset | Purpose | Default execution |
| --- | --- | --- |
| `jacobian/agent-workflow-v1` | Fixed Jacobian-enabled mathematical workflows | Oracle and optional observation |
| `jacobian/public-reproductions-v1` | Replay known public mathematical cases | Oracle |
| `jacobian/research-diagnostics-v1` | Answer-visible research challenges | Oracle diagnostics |
| `jacobian/performance-v1` | Historical pinned runtime baseline | Oracle |
| `jacobian/provider-feasibility-v1` | Pinned optional-backend checks | Oracle |
| `jacobian/examples-v1` | Tutorial and smoke workflows | Oracle |

`registry.toml` is the discovery index. Each dataset's `suite.toml` owns its
nested task membership and assurance ceilings. `dataset.toml` is generated
from that manifest and Harbor-computed task digests; hand-editing digests is a
validation error. Harbor jobs are rendered with explicit task paths because
Harbor's local dataset loader does not recurse through the domain/field tree.

The repository `.uv-version` pins active development, CI, release, and product
image builds. Harbor task images remain bound to the uv version and digest in
their published task identity; changing that environment requires a new task
digest and Oracle validation. In particular, `performance-v1` declares its
historical source and toolchain in `baseline.toml` rather than pretending to
measure current main.

Tasks expose only `instruction.md` and `environment/` to an evaluated agent.
Oracle solutions remain under `solution/`; verifier code and fixtures remain
under `tests/`. No compatibility directories or aliases for the former
benchmark layout are retained.

## Commands

```sh
make harbor-check
make harbor-sync
make harbor-oracle DATASET=agent-workflow-v1
make harbor-oracle-all
make agent-eval DATASET=agent-workflow-v1 EVAL_EXECUTE=1
make performance-eval
make provider-eval PROVIDER=cgal
```

Performance timing is reported separately from reward, and research datasets
are explicitly non-comparative diagnostics. Uniform task structure does not
make rewards across these datasets comparable.

See [authoring a Harbor benchmark task](../docs/how-to/author-harbor-benchmark-task.md),
[reference benchmarks](../docs/reference/benchmarks.md), and the
[Harbor benchmarks skill](../.agents/skills/harbor-benchmarks/SKILL.md).
