# Author a Harbor benchmark task

[Documentation home](../index.md)

Executable benchmark cases live under
`benchmarks/datasets/<dataset>/tasks/<domain>/<field>/<task>/`. Start from
`benchmarks/templates/task/`, then choose the dataset whose claim matches the
case.

Freeze agent-visible input and the strict submission schema under
`environment/`. Keep expected answers and solution material under `solution/`,
and the clean-room verifier plus fixtures under `tests/`. Add the nested
relative path, global task ID, assurance ceiling, and provider requirement to
the dataset's `suite.toml`.

Run `make harbor-sync`, inspect the generated `dataset.toml` and rendered job
paths, then run `make harbor-check` and
`make harbor-oracle DATASET=<dataset-directory-name>`.

Do not add task symlinks, legacy aliases, or a second fixture home. The task
README is maintainer context and is not injected into a trial. Instructions
describe the requested outcome without prescribing Jacobian capabilities or a
research strategy.

Verifier attack tests should cover malformed and unknown fields, wrong answers,
scope and completeness mismatches, forged or escaped evidence, digest mismatch,
and false assurance. A task may accept `VERIFIED` only when an
operator-authorized checker independently binds the exact claim and evidence.
After changing a task contract, verifier, dependency, or image, regenerate its
Harbor digest and rerun its Oracle.
