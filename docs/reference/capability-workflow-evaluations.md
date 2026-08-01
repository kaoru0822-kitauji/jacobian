# Capability workflow evaluations

[Documentation home](../index.md)

Jacobian packages executable evaluation cases into the six Harbor datasets
listed in [`benchmarks/README.md`](../../benchmarks/README.md). The comparison
plan and discovery handoffs for capability research live separately in
[`research/evaluations/capability-workflow-v1/`](../../research/evaluations/capability-workflow-v1/).
Dataset identity is a claim boundary: workflow observations, public
reproductions, answer-visible research diagnostics, runtime measurements,
provider feasibility, and examples must not share an interpretation merely
because they use one task format.

The ownership boundary is deliberate. `benchmarks/datasets/` contains
executable Harbor cases, `benchmarks/tooling/` contains reusable Harbor
infrastructure, and `research/evaluations/` contains non-runnable plans,
discovery handoffs, and reports. Research records may point at a canonical
dataset, but they do not duplicate its tasks, become Harbor job input, or enter
an agent container.

## Task and verifier validation

Every task has frozen agent-visible input, schema 1.4 metadata, an Oracle-only
solution, and a separate clean-room verifier. The repository suite module
validates `registry.toml`, suite headers, and member fragments, resolves
canonical task IDs, computes Harbor-native digests, checks visibility, and
renders explicit task paths:

```sh
make benchmark-check
make benchmark-oracle DATASET=agent-workflow-v1
```

The verifier scores only evidence its contract authorizes. Timeout,
cancellation, errors, incomplete enumeration, and missing witnesses are
non-conclusions. An Oracle answer does not authorize `VERIFIED`.

## Workflow observations and diagnostics

Use the fixed `agent-workflow-v1` tasks for Jacobian workflow observations:

```sh
make agent-eval DATASET=agent-workflow-v1 EVAL_EXECUTE=1
```

Keep any future control/treatment comparison in Harbor job configuration,
outside task bundles, with identical task digests, prompts, models, budgets,
environments, and seeds.

Use `research-diagnostics-v1` only for answer-visible diagnostic runs. Its
public source answers and Oracle summaries remain hidden from the agent
container at runtime, but their public availability permanently disqualifies
the dataset from held-out model claims.

## Reproducible handoff

Record the git tree, suite and task digests, provider/runtime profile, model and
prompt settings, raw trace location, validation actually run, unresolved proof
obligations, and next action. Publishing a local dataset to a Harbor registry
requires separate authorization.
