# Milestone 4 specification: claim-transformation primitives

[Documentation home](../../index.md)

- Status: Provisional implementation; outside v0.2 conformance
- Theme: Give AI agents and human researchers composable operations for
  developing and challenging claims

## 1. Entry gate

Scalable search must reliably preserve verified counterexamples,
constructions, and transformation lineage.

## 2. Current implementation and target decomposition

The provisional implementation exposes three hypothesis-producing commands
through one optional `HypothesisTransformer` plugin capability. This is the
current compatibility surface, not the target primitive boundary.

M4 should expose separately composable operations for:

- deriving a claim from a source claim and a typed edit;
- generating claims under a domain-owned grammar;
- deduplicating claims within a declared reference set;
- scoring or ranking hypotheses under a named heuristic;
- requesting bounded falsification;
- proposing and checking parameter conditions.

The plugin owns the mathematical grammar, solver, enumerator, and heuristics.
The kernel owns schema validation, exact source lineage, identity, budgets, and
authorized-checker dispatch. Agent workflows choose how to compose the
operations and whether to route a hypothesis into M3 falsification.

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

The current command composes four stages: generate candidate formal statements
under a plugin-owned typed grammar, deduplicate them within the active
experiment or supplied reference set, request a search for immediate
counter-witnesses, and rank surviving hypotheses. Each stage must remain
inspectable and retain its own execution and assurance record.

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
checker emits a certificate verification record bound to the exact region.
Jacobian first stores an immutable region subject containing the target claim,
relation, and canonical conditions. `parameter.region.promote` replays that
certificate with its authorized checker and accepts only the identical
verification-record URI before returning a verified sufficient or necessary
label.
Artifacts cited as samples must be supplied explicitly as workflow evidence;
plugin output cannot introduce or relabel unrelated stored artifacts.

### `parameter.region.promote`

Promotion is a kernel verification operation, not a hypothesis-plugin
capability. It accepts an immutable parameter-region subject URI and a
verification-record URI. The service requires:

- the subject schema and its declared claim/sample lineage;
- matching claim and subject semantics;
- certificate evidence with conclusion `TRUE`;
- claim and candidate object digests bound to the exact subject payload;
- the exact subject and declared claim artifact URIs in the verification
  record's parents;
- successful replay that reproduces the supplied verification-record URI.

The exact artifact-parent checks matter because two artifacts may have equal
object digests while carrying different lineage or summary metadata. Promotion
returns the label implied by the subject's `SUFFICIENT` or `NECESSARY` kind only
after all checks pass.

## 3. Example workflow

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

No kernel-owned synthesis framework or evolutionary-search runtime is required.
An agent workflow composes immutable artifacts, installed plugin operations,
and the M3 experiment service.

## 4. Implemented scope and limits

The provisional implementation provides the three compatibility commands,
exact source-record replay, immutable edit and transformation records,
request-local deduplication, optional M3 falsification, sampled-evidence
lineage, and explicit parameter-region promotion through Python, CLI, and MCP
surfaces.

It does not define a universal conjecture grammar, global novelty measure,
parameter-region proof format, or domain-independent meaning for sufficient and
necessary conditions. Authorized domain checkers own that mathematics. M5
corpus integration remains optional and unimplemented.

See
[ADR 0004](../../explanation/adr/0004-verified-parameter-regions.md)
for the immutable subject and exact-carrier decision.

## 5. Exit gate

Milestone 4 is complete when:

- every generated statement has a precise source and transformation record;
- one synthetic plugin implements all three hypothesis operations without
  kernel or MCP changes;
- claim derivation, deduplication, scoring, and falsification can be invoked
  and inspected as distinct stages;
- generated and repaired statements remain hypotheses;
- immediate counterexamples are stored with verified witnesses;
- parameter claims distinguish proved and sampled regions;
- generation, ranking, and non-falsification are never displayed as proof;
- every workflow remains usable without a research-corpus provider.
