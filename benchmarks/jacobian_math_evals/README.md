# Jacobian math evaluations

Internal Harbor adapter. Compiles versioned source catalog plus 18
answer-visible research diagnostics into deterministic Harbor 1.4 tasks. Does
not publish datasets or run paid agent rollouts.

## Generate

```sh
uv run python -m benchmarks.jacobian_math_evals.main \
  --split smoke \
  --output-dir tmp/jacobian-math-evals
```

CLI supports `--output-dir`, `--limit`, `--overwrite`, `--task-ids`,
`--source-ids`, `--split`, `--cache-dir`, and `--offline`. Splits: `public`,
`coverage`, `train`, `dev`, `test`, `full`, `smoke`.

`coverage` fails closed until every catalog record has a meaningful task and a
non-null oracle. Supported immutable snapshots produce source-row diagnostics.
Unavailable, gated-without-rows, and tool-only records use checked-in,
manually-authored mathematical family instances, grouped only within the same
contamination partition. These are explicitly labeled as family-level cases;
they do not pretend to reproduce an unavailable upstream row. `public` emits
the 18 curated research diagnostics plus supported answer-visible rows.
Generated task directories stay uncommitted.

Normal generation freezes only bounded rows. `full` uses Dataset Viewer
`/size` and paginated `/rows` responses, checks the Hub revision before and
after the stream, and digest-caches each page. Offline `full` fails if its
manifest or any page is missing; it never silently treats `first-rows` as the
complete dataset.

## Environment

Agent env: Python 3.12, no network, 2 CPUs, 4 GiB RAM, 1800-second timeout.
Frozen instance metadata copied to `/app/input`. Restricted or unresolved
sources marked non-publishable; raw snapshots never included.

## Verifier

Reward Kit runs in separate no-network verifier image. Harbor transfers only
`/app/submission.json`, `/app/evidence`, plus conventional artifact dir. Hidden
fixtures stay in verifier image.

| Reward | Type | Meaning |
| --- | --- | --- |
| `correctness` | Programmatic | Conclusion matches exact oracle contract. |
| `evidence_validity` | Programmatic | Evidence exists; SHA-256 matches. |
| `scope_accuracy` | Programmatic | Submission binds required source/task scope. |
| `assurance_calibration` | Programmatic | Claimed assurance respects authority. |
| `reward` | Programmatic | 70/10/10/10; wrong answer or false certification forces zero. |

No reward depends on tool use/call order. Public diagnostics stay separate from
held-out scored partitions.

## Layout

Each generated task contains `task.toml`, `instruction.md`, offline
`environment/Dockerfile`, Oracle-only `solution/`, clean-room Reward Kit
criteria under `tests/`. `generation-manifest.json` records task/source mapping
and redistribution eligibility. The
[catalog contract](catalog/README.md) defines committed provenance, cache
boundaries, and coverage labels.

## Current validation status

Repository tests exercise catalog parsing, handlers, deterministic generation,
submission verification, matched configuration, telemetry, and acceptance
gates. No committed result currently demonstrates a complete coverage-suite
Oracle run or a control/treatment model rollout. Do not treat task generation,
unit-test success, or source references as rollout evidence.

After verifier, verifier dependency, generated Dockerfile, or task-contract
changes, rerun the affected Oracle suite. Record the exact tree, catalog and
policy digests, dependency lock, image digest, task manifest, and validation
results before making benchmark claims.

## Run

```sh
harbor run -t tmp/jacobian-math-evals/<task-directory> -a oracle
```

Paid trials remain deferred until acquisition locks, Oracle validation,
negative-path checks, and leakage scans pass.

Refresh public provenance metadata with:

```sh
uv run python -m benchmarks.jacobian_math_evals.acquisition
```

GitHub resolution uses authenticated `gh` REST reads. Hugging Face resolution
uses Hub plus Dataset Viewer APIs for immutable revisions, configs, splits,
sizes, gating, licenses, and parquet URLs. Unsupported or failed sources remain
explicitly `unresolved`.

Probe Hugging Face schemas and freeze bounded Dataset Viewer snapshots:

```sh
uv run python -m benchmarks.jacobian_math_evals.probe_huggingface
```

Scalar answer rows use the exact-answer handler. Explicit structured schemas
route to proof repair, proof completion, premise retrieval, statement
alignment, or tool application. Nested chat rows require a user/assistant pair.
Ambiguous schemas are never guessed.

## Matched evaluation

`configs.write_matched_configs` emits current-Harbor control and treatment
JobConfigs plus a deterministic paired-order manifest. Treatment adds only the
toolbox instruction, per-trial compose service, and Jacobian MCP entries.
The compose file requires a digest-pinned `JACOBIAN_IMAGE`, an opaque
`JACOBIAN_MCP_TOKEN`, and `JACOBIAN_AUTH_TOKENS_JSON`; Caddy injects the bearer
header without exposing it to the task prompt. Configuration generation
validates those values before writing the treatment JobConfig. Jacobian starts
stateless HTTP with `COMPUTE_VERIFY_NO_RETRIEVAL` and a per-compose-project
state volume.

Observable process events and trial provenance use the schemas under
`schemas/`. Hidden reasoning is neither requested nor analyzed.
