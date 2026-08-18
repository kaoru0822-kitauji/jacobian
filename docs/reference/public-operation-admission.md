# Public mathematical operation admission

[Documentation home](../index.md)

- Status: Current catalog-maintenance contract
- Reviewed catalog base: `61589543bbbff546edbc51d34a07887982fa4ad6`
- Machine-readable ledger: `src/jacobian/catalog/admission.py`

The public `math.find` / `math.run` catalog is a curated basis of mathematical
operations, not an inventory of every callable helper in `jacobian.math` or in
an installed backend. Every candidate declaration must have exactly one
admission decision before it can enter the catalog. Catalog construction fails
closed when the candidate inventory and decision ledger disagree.

## Admission gates

A public operation must satisfy every gate:

1. It exposes one stable mathematical map, predicate, invariant, construction,
   search, or check rather than a problem-solving workflow.
2. The caller retains representation, decomposition, sequencing, proof
   strategy, and stopping decisions.
3. It returns a reusable typed value, witness, or certificate rather than a
   report or suggested next action.
4. It is exact and bounded, or its result has explicit typed
   `INCOMPLETE`, `UNKNOWN`, or `TRUNCATED` semantics.
5. Its mathematical identity is durable and independent of a benchmark,
   conjecture, theorem instance, or current model behavior.
6. It supplies material computation or reliability leverage over ordinary
   model-authored Python.
7. It is not merely a cheap deterministic projection of another public result.
   Useful projections normally belong only in the native API.
8. Its schema contains no benchmark constants, theorem-specific answer shape,
   or frozen research workflow.
9. It has a distinct discovery intent and does not create a near-duplicate
   result that degrades retrieval.

Passing schema validation, having tests, or wrapping a maintained library does
not by itself satisfy these gates.

## Decisions

The exhaustive ledger uses five decisions:

| Decision | Catalog effect | Required disposition |
| --- | --- | --- |
| `KEEP` | Public | Preserve the operation ID and contract. |
| `NATIVE_ONLY` | Excluded | Keep the useful deterministic helper under an explicit supported `jacobian.math` symbol. |
| `SPLIT` | Excluded | Do not expose the aggregate; admit smaller outcomes only after independent evidence establishes their discovery intent and leverage. |
| `DROP` | Excluded | Retain no supported public interface solely for compatibility or coverage. |
| `CONTRACT_FIX` | Excluded | Repair the named correctness defect and add an adversarial regression, then reclassify the operation before publication. |

The final 2026-08-17 audit classifies all 360 candidate declarations: 200
`KEEP`, 56 `NATIVE_ONLY`, and 104 `DROP`. No unresolved `SPLIT` or
`CONTRACT_FIX` decision is published. The Nash-equilibrium and stationary-
distribution repairs were reclassified to `KEEP`; three coherent profile
results initially marked `SPLIT` were also retained after re-review. A decision
is not inherited by a renamed or materially changed operation; such a candidate
needs a fresh row.

The same review covered every open mathematical pull request at its frozen head;
see the [dated open-PR audit](open-math-pr-audit-2026-08-17.md).

## Migration from the uncurated catalog

Consumers must rediscover operations against the current catalog instead of
assuming that every previous candidate remains callable. A `NATIVE_ONLY` row's
`native_symbol` names its supported `jacobian.math` replacement; a `DROP` row
has no compatibility operation. The schema snapshot records the complete set of
200 public IDs.

Three retained contracts also changed during the audit:

- `game_theory.nash_equilibrium.compute` version 2 uses exact primal and dual
  linear programs, including for games with negative values.
- `probability.markov_chain.stationary_distribution.compute` version 2 returns
  the extreme stationary distribution for every closed communicating class and
  states whether the family is unique. The singular native
  `stationary_distribution` helper rejects non-unique chains; use
  `stationary_distribution_extremes` for the complete family.
- `metric_space.profile.compute` version 2 reports
  `DIRECT_DISTANCE_MATRIX_SCAN`, matching its direct scan of the supplied
  distance matrix.

## Review procedure

For a catalog-changing pull request:

1. Compare the candidate against nearby IDs, native symbols, input and output
   types, and discovery wording.
2. Record one decision and a concrete mathematical rationale in the ledger.
3. For `NATIVE_ONLY`, name an importable callable whose containing public
   module includes it in `__all__`.
4. For bounded search, test both a complete result and the applicable
   incomplete or truncated path. Missing witnesses and exhausted budgets are
   never negative mathematical conclusions.
5. Regenerate the schema snapshot and run the catalog, native-API, and owning
   mathematical tests.

Do not use the ledger as a dynamic recommendation or runtime policy layer. It
is a source review record that determines the explicit immutable built-in
catalog; `math.find` remains stateless discovery over that result.
