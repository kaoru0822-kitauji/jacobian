# Milestone 4 specification: conjecture workflows

- Status: Provisional
- Theme: Give agents tools for developing conjectures

## 1. Entry gate

Scalable search must reliably preserve verified counterexamples,
constructions, and transformation lineage.

## 2. New tools

### `conjecture.repair`

Given a verified counterexample, propose nearby claims by changing one declared
dimension at a time:

- assumptions;
- constants;
- quantified domain;
- graph or structure class;
- conclusion strength.

Each proposal records its edit relative to the source claim and begins with
`verification = UNVERIFIED`.

### `conjecture.generate`

Generate candidate formal statements under a typed grammar, deduplicate them
within the active experiment or supplied reference set, search for immediate
counter-witnesses, and rank surviving hypotheses.

Interestingness, apparent novelty, and failure to find a counterexample are
research heuristics, not assurance. Without an M5 corpus provider, global
novelty is reported as `UNKNOWN`.

### `parameter.generalize`

Starting from a verified finite construction, derive a proposed exact parameter
region using symbolic elimination, rational constraints, or certified interval
methods.

The output separates:

- proposed parameter conditions;
- proven sufficient conditions;
- proven necessary conditions;
- sampled or unknown regions.

## 3. Workflow

```text
verified result
    → proposed repair, generalization, or new claim
    → claim.validate
    → falsification and bounded search
    → witness or certificate verification
    → experiment record
```

The workflow may consult an M5 corpus provider when one is configured, but its
correctness and verification boundary do not depend on one.

## 4. Exit gate

Milestone 4 is complete when:

- every generated statement has a precise source and transformation record;
- generated and repaired statements remain hypotheses;
- immediate counterexamples are stored with verified witnesses;
- parameter claims distinguish proved and sampled regions;
- generation, ranking, and non-falsification are never displayed as proof;
- every workflow remains usable without a research-corpus provider.
