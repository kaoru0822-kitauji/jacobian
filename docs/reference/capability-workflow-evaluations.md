# Capability workflow evaluations

[Documentation home](../index.md)

Jacobian packages executable evaluation cases into six Harbor datasets listed
in [`benchmarks/README.md`](../../benchmarks/README.md). Dataset identity is a
claim boundary: workflow observations, public reproductions, answer-visible
research diagnostics, runtime measurements, provider feasibility, and examples
must not share an interpretation merely because they use one task format.

## Task and verifier validation

Every task has frozen agent-visible input, schema 1.4 metadata, an Oracle-only
solution, and a separate clean-room verifier. The repository suite module
validates `registry.toml` and `suite.toml`, resolves nested task paths, computes
Harbor-native digests, checks visibility, and renders explicit task paths:

```sh
make harbor-check
make harbor-oracle DATASET=agent-workflow-v1
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
