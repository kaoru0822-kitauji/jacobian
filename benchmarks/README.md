# Jacobian Harbor datasets

Every executable benchmark case is a self-contained Harbor task. The six
dataset identities below keep workflow observations, public reproductions,
research diagnostics, operational measurements, provider feasibility, and
examples from making incompatible claims look comparable.

`benchmarks/tasks/` is the sole home for canonical executable Harbor bundles.
`benchmarks/datasets/<dataset>/members/` selects those bundles without copying
them; `suite.toml` contains dataset metadata and `dataset.toml` is generated.
Reusable Harbor infrastructure belongs under `benchmarks/tooling/`, adapters
under `benchmarks/adapters/`, and non-runnable evaluation plans and research
handoffs under `research/evaluations/`.

| Dataset | Purpose | Default execution |
| --- | --- | --- |
| `jacobian/agent-workflow-v1` | Fixed Jacobian-enabled mathematical workflows | Oracle and optional observation |
| `jacobian/public-reproductions-v1` | Replay known public mathematical cases | Oracle |
| `jacobian/research-diagnostics-v1` | Answer-visible research challenges | Oracle diagnostics |
| `jacobian/performance-v1` | Controlled runtime measurements | Oracle |
| `jacobian/provider-feasibility-v1` | Pinned optional-backend checks | Oracle |
| `jacobian/examples-v1` | Tutorial and smoke workflows | Oracle |

`registry.toml` is the discovery index. Each dataset's member fragments own
membership and assurance ceilings. `dataset.toml` is generated from those
fragments and Harbor-computed task digests; hand-editing digests is a
validation error. Harbor jobs are rendered with explicit flat task paths.

Tasks expose only `instruction.md` and `environment/` to an evaluated agent.
Oracle solutions remain under `solution/`; verifier code and fixtures remain
under `tests/`. No compatibility directories or aliases for the former
benchmark layout are retained.

## Commands

```sh
make benchmark-plan BASE=origin/main
make benchmark-sync
make benchmark-check
make benchmark-oracle DATASET=agent-workflow-v1 TASKS="task-id"
make benchmark-oracle-all
make agent-eval DATASET=agent-workflow-v1 EVAL_EXECUTE=1
make performance-eval
make provider-eval PROVIDER=cgal
```

Pull requests run contract checks and exact Oracles for changed executable
tasks; large multi-task edits defer that matrix to the merge queue. Merge-queue
groups add affected-dataset or shared-infrastructure Oracle
coverage, while pushes to `main` repeat the deterministic contract gate without
duplicating those Docker jobs. The weekly and manually dispatched benchmark
workflow performs the full portfolio sweep; maintainers can request the same
scope on a pull request with `ci:benchmark-full`.

Performance timing is reported separately from reward, and research datasets
are explicitly non-comparative diagnostics. Uniform task structure does not
make rewards across these datasets comparable.

See [authoring a Harbor benchmark task](../docs/how-to/author-harbor-benchmark-task.md),
[reference benchmarks](../docs/reference/benchmarks.md), and the
[Harbor benchmarks skill](../.agents/skills/harbor-benchmarks/SKILL.md).
