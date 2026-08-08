# Multi-tool mathematical coordination study

This public workflow observation asks whether individually useful Jacobian
operations are discovered and composed into mathematically valid terminal
objects. It transfers the central evaluation lesson from Chen et al.,
*Learning to Coordinate Symbolic Tools*: local symbolic correctness does not
determine global operation choice, ordering, representation handoff, recovery,
or stopping. It does not transfer that paper's synthetic training corpus,
tool-call reward, SFT, or GRPO procedure.

## PR1 preregistration

The frozen
[`multi-tool-coordination-pr1.json`](../../../benchmarks/config/multi-tool-coordination-pr1.json)
selects six existing `mathematical-benchmarks-v1` tasks across graph theory,
algebraic topology, polynomial algebra, optimization, geometry, and integer
linear algebra. Each task receives two independent locally authenticated Codex
rollouts with `gpt-5.4-mini`, medium reasoning, REQUIRED external reasoning
logs, a 600-second process limit, no web search, and no wrong-answer retry.

The task matrix probes graph/set/artifact composition, complex-to-chain and
lattice handoff, polynomial-map candidate checking, rational/positive-definite
slice evidence, coordinate-to-polynomial proof repair, and normal-form
transformation checking. The task instructions remain agent-owned and do not
prescribe a tool sequence.

The normal Harbor observation runner requires Docker, which is unavailable on
the collection host. The preregistered host-local fallback therefore makes no
Harbor execution claim. It exposes only `instruction.md`, `input.json`, and
`submission_schema.json` in a fresh workspace; starts a fresh REQUIRED-log MCP
runtime and state directory per rollout; runs Codex without user configuration
or an API key; and invokes the unchanged task-owned verifier afterward through
the repository's fresh-interpreter virtual-mount harness. This is public
workflow evidence, not a held-out or causal performance comparison.

Only full task-verifier reward is `ACCEPTED`. A completed zero/partial reward is
`REJECTED`. Timeout, model error, verifier infrastructure error, missing model
output, or incomplete execution is `INCONCLUSIVE`, never a negative label.
Tool calls, tokens, and reasoning-log events have reward zero. The analysis
classifies capability discovery, order, intermediate recognition,
representation handoff, checker use, scope/completeness interpretation,
rejection recovery, repeated work, and possible reusable operation gaps only
after all declared rollouts are preserved.

Execution is opt-in and must occur inside a named `tmux` session:

```sh
uv run --locked --with harbor==0.20.0 --with tomli-w==1.2.0 \
  --with jsonschema python -m benchmarks.tooling.multi_tool_coordination_study run \
  --spec benchmarks/config/multi-tool-coordination-pr1.json \
  --output benchmarks/results/multi-tool-coordination-pr1 --execute
```
