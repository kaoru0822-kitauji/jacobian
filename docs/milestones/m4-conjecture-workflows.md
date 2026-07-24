# Milestone 4 specification: conjecture workflows

- Status: Provisional
- Theme: Give agents tools for developing conjectures

## 1. Entry gate

Scalable search must reliably preserve verified counterexamples,
constructions, and transformation lineage.

## 2. Shared plugin operation

All three M4 tools use one optional `HypothesisTransformer` plugin capability.
The operation is typed as repair, generation, or parameter generalization, but
the plugin owns its grammar, solver, enumerator, or heuristic. The kernel owns
schema validation, exact source lineage, deduplication, budgets, and routing
back into the M3 falsification loop.

### `conjecture.repair`

Given a verified counterexample, propose nearby claims by changing one declared
dimension at a time:

- assumptions;
- constants;
- quantified domain;
- graph or structure class;
- conclusion strength.

Each proposal records its edit relative to the source claim and begins with
`verification = UNVERIFIED`. The source record must have been emitted by an
operator-authorized checker, must bind the exact source claim, and must cite a
`REFUTES_CLAIM` witness.

### `conjecture.generate`

Generate candidate formal statements under a plugin-owned typed grammar,
deduplicate them within the active experiment or supplied reference set,
search for immediate counter-witnesses, and rank surviving hypotheses.

Interestingness, apparent novelty, and failure to find a counterexample are
research heuristics, not assurance. Without an M5 corpus provider, global
novelty is reported as `UNKNOWN`.

Jacobian does not define a universal conjecture grammar or ranking model.
Duplicate claims collapse through their content address, and surviving claims
re-enter ordinary `claim.validate` and `search.run`.

### `parameter.generalize`

Starting from a verified finite construction, propose an exact parameter
region using symbolic elimination, rational constraints, certified interval
methods, or another plugin method.

The output separates:

- proposed parameter conditions;
- proven sufficient conditions;
- proven necessary conditions;
- sampled or unknown regions.

A plugin may report only proposed or sampled region evidence. Sufficient or
necessary conditions become verified only when a compatible independent
checker emits a verification record bound to the exact region.
Artifacts cited as samples must be supplied explicitly as workflow evidence;
plugin output cannot introduce or relabel unrelated stored artifacts.

## 3. Workflow

```text
verified result
    → proposed repair, generalization, or new claim
    → claim.validate
    → search.run for falsification
    → witness or certificate verification
    → immutable experiment and transformation records
```

The workflow may consult an M5 corpus provider when one is configured, but its
correctness and verification boundary do not depend on one.

No workflow engine, synthesis framework, or evolutionary-search runtime is
required. M4 composes immutable artifacts, the installed plugin boundary, and
the M3 experiment service.

## 4. Exit gate

Milestone 4 is complete when:

- every generated statement has a precise source and transformation record;
- one synthetic plugin implements all three operations without kernel or MCP
  changes;
- generated and repaired statements remain hypotheses;
- immediate counterexamples are stored with verified witnesses;
- parameter claims distinguish proved and sampled regions;
- generation, ranking, and non-falsification are never displayed as proof;
- every workflow remains usable without a research-corpus provider.
