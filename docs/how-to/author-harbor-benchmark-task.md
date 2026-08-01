# Author a Harbor benchmark task

[Documentation home](../index.md)

Executable benchmark cases live once under `benchmarks/tasks/<task-id>/`.
Choose a globally unique flat task ID; keep domain, field, provenance, and
evaluation classification in `task.toml` metadata. Add one member fragment at
`benchmarks/datasets/<dataset>/members/<task-id>.toml` for every dataset that
owns the case. Start from `benchmarks/templates/task/`, then choose the
dataset whose claim matches the case.

Freeze agent-visible input and the strict submission schema under
`environment/`. Keep expected answers and solution material under `solution/`,
and the clean-room verifier plus fixtures under `tests/`. The member fragment
declares only the canonical task ID, assurance ceiling, and provider
requirement; `dataset.toml` is generated.

Run `make benchmark-plan BASE=origin/main`, then `make benchmark-sync`, inspect
the generated `dataset.toml` and rendered job paths, and run
`make benchmark-check` followed by
`make benchmark-oracle DATASET=<dataset-id> TASKS="<task-id>"`.

Do not add task symlinks, aliases, or a second fixture home. The task
README is maintainer context and is not injected into a trial. Instructions
describe the requested outcome without prescribing Jacobian capabilities or a
research strategy.

Verifier attack tests should cover malformed and unknown fields, wrong answers,
scope and completeness mismatches, forged or escaped evidence, digest mismatch,
and false assurance. A task may accept `VERIFIED` only when an
operator-authorized checker independently binds the exact claim and evidence.
After changing a task contract, verifier, dependency, or image, regenerate its
Harbor digest and rerun its Oracle.
