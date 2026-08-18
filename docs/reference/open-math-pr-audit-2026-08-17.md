# Open mathematical pull-request admission audit — 2026-08-17

This audit compares every open mathematics pull request against
`origin/main` at `61589543bbbff546edbc51d34a07887982fa4ad6` and applies the
[public operation admission gates](public-operation-admission.md). Head SHAs
are frozen below so later revisions require a fresh review.

## Current-catalog re-review

The final curation classifies all 360 installed candidates as 200 `KEEP`, 56
`NATIVE_ONLY`, and 104 `DROP`. No unresolved `SPLIT` or `CONTRACT_FIX` row is
published.

The re-review restored three coherent complete results that had been excluded
too aggressively: the point-distance multiplicity profile, finite-metric
profile, and numerical-semigroup gap profile. It also moved five cheap
projections out of MCP discovery: convergents, biconnected components, strongly
connected components, graph radius, and DFA complement. Their useful functions
remain supported under `jacobian.math`. Classical combinatorial numbers, basic
formal-series transformations, and finite-metric balls were similarly moved to
explicit native APIs instead of being discarded.

The two base-catalog contract repairs now satisfy `KEEP`: finite zero-sum Nash
equilibria use exact primal-dual linear programming, including negative-valued
games, and finite Markov chains return every extreme stationary distribution
rather than one arbitrary eigenvector. The finite-metric profile's false
`FLOYD_WARSHALL` method claim was also replaced with its actual direct-matrix
scan semantics.

| PR | Frozen head | Overall decision | Required change |
| --- | --- | --- | --- |
| [#1965](https://github.com/morluto/jacobian/pull/1965) | `353467811f893c4ebd05137615b31784acad2e70` | `SPLIT` | Keep the full Grundy table, birthday, and bounded subtraction Grundy prefix; move/drop table projections and elementary Nim helpers. |
| [#1966](https://github.com/morluto/jacobian/pull/1966) | `46531dc977eaeec3824aac9d1375d5a16c59d227` | `SPLIT` | Keep the complete factor family, period structure, and morphism incidence matrix; make direct word/morphism helpers native-only. Remove unrelated numerical-semigroup changes. |
| [#1967](https://github.com/morluto/jacobian/pull/1967) | `122ebf4a0e4769fd425af4ae7d317e8e71c75710` | `CONTRACT_FIX` | Give bounded orbit prefixes an explicit typed truncation/completeness contract and drop the fixed-point-equation projection. Remove unrelated numerical-semigroup changes. |
| [#1968](https://github.com/morluto/jacobian/pull/1968) | `f21ee755a35bf497ffa276a515c6c25cea4cd4db` | `SPLIT` | Separate the adjacency presentation from essentiality, period, and mixing projections. Remove unrelated numerical-semigroup changes. |
| [#1969](https://github.com/morluto/jacobian/pull/1969) | `87daaa1d80f8dd1452982ae19da1d077ae9addd2` | `CONTRACT_FIX` | Replace the heuristic Betti bound and repair the claimed minimal presentation/binomial semantics before exposing any global invariants. |
| [#1970](https://github.com/morluto/jacobian/pull/1970) | `f52e2466bb371ff82d742642ba7237af42886564` | `SPLIT` | Keep run, composition, and path replay; retain identity, trim, and inverse only as native helpers. Remove unrelated poset changes. |
| [#1971](https://github.com/morluto/jacobian/pull/1971) | `0bee805c2ae8c36a771eb088136441cd01fbbbbc` | `SPLIT` | Keep specialization preorder, components, continuity, and beat points; closure/interior are native projections. Remove unrelated poset changes. |
| [#1972](https://github.com/morluto/jacobian/pull/1972) | `0c8c4996ad2716824b7bd4e9f0bac860161ffb74` | `CONTRACT_FIX` | Preserve a typed frontier and explicit completeness basis for truncated reachability; keep firing public and move enabled/incidence helpers native-only. Remove unrelated poset changes. |
| [#1973](https://github.com/morluto/jacobian/pull/1973) | `52218741f0863429c04ea7aafc9a82bf7f877980` | `SPLIT` | Keep factor multiplication, marginalization, and d-separation; omit the multi-step variable-elimination workflow. Remove unrelated poset changes. |
| [#1974](https://github.com/morluto/jacobian/pull/1974) | `499ec04b96a78539665d95081b8a3f94eb7e0177` | `SPLIT` | Keep matching and unification; replace the hard-coded leftmost-outermost step with an explicit redex/rule choice or all one-step results, and keep normal-form iteration native-only. Remove unrelated poset changes. |
| [#1975](https://github.com/morluto/jacobian/pull/1975) | `43b74c73190a855e47a7770e943aa11f9b3d533c` | `KEEP` | Both tree run and fixed-size accepted-tree count are distinct exact bounded outcomes. Remove unrelated poset changes before merge. |

## Operation-level decisions

### PR #1965 — impartial games

| Operation | Decision | Reason |
| --- | --- | --- |
| `game.impartial.grundy_table.compute` | `KEEP` | Complete reusable Grundy assignment for one finite DAG. |
| `game.impartial.position.grundy.compute` | `DROP` | Projection of the full table. |
| `game.impartial.outcome_profile.compute` | `DROP` | P/N partition is a deterministic projection of Grundy values. |
| `game.impartial.nim_equivalent.compute` | `DROP` | Renames one position's Grundy value. |
| `game.impartial.grundy_classes.compute` | `DROP` | Groups the full table by value. |
| `game.impartial.birthday.compute` | `KEEP` | Distinct exact DAG-height invariant. |
| `game.nim.nim_sum.compute` | `NATIVE_ONLY` | One XOR reduction. |
| `game.nim.options.compute` | `NATIVE_ONLY` | Direct finite tuple enumeration. |
| `game.subtraction.dag.compute` | `NATIVE_ONLY` | Mechanical representation construction. |
| `game.subtraction.grundy_prefix.compute` | `KEEP` | Complete bounded recurrence result. |
| `combinatorics.mex.compute` | `NATIVE_ONLY` | Small deterministic helper. |

### PR #1966 — combinatorics on words

| Operation | Decision |
| --- | --- |
| `word.factors.length.compute` | `KEEP` |
| `word.periods.compute` | `KEEP` |
| `word_morphism.incidence_matrix.compute` | `KEEP` |
| `word.factor_occurrences.compute` | `NATIVE_ONLY` |
| `word.primitive_root.compute` | `NATIVE_ONLY` |
| `word.conjugates.compute` | `NATIVE_ONLY` |
| `word.parikh_vector.compute` | `NATIVE_ONLY` |
| `word.prefix_function.compute` | `NATIVE_ONLY` |
| `word_morphism.apply.compute` | `NATIVE_ONLY` |
| `word_morphism.compose.compute` | `NATIVE_ONLY` |

### PR #1967 — arithmetic dynamics

| Operation | Decision | Reason |
| --- | --- | --- |
| `arithmetic_dynamics.map.iterate.compute` | `KEEP` | Exact fixed iterate. |
| `arithmetic_dynamics.point.orbit.compute` | `CONTRACT_FIX` | No repeat within the requested prefix must be typed as truncated, not silently complete. |
| `arithmetic_dynamics.fixed_point_equation.compute` | `DROP` | Cheap subtraction from the retained iterate. |
| `arithmetic_dynamics.dynatomic_polynomial.compute` | `KEEP` | Distinct exact invariant. |
| `arithmetic_dynamics.cycle.multiplier.compute` | `KEEP` | Distinct cycle invariant. |
| `arithmetic_dynamics.finite_field.functional_graph.compute` | `KEEP` | Complete bounded finite-field construction. |

### PR #1968 — symbolic dynamics

| Operation | Decision |
| --- | --- |
| `symbolic_dynamics.finite_type_shift.construct` | `KEEP` |
| `symbolic_dynamics.block_language.compute` | `KEEP` |
| `symbolic_dynamics.adjacency_shift.construct` | `SPLIT` |
| `symbolic_dynamics.periodic_point_profile.compute` | `KEEP` |
| `symbolic_dynamics.higher_block.compute` | `KEEP` |

The adjacency result currently combines a matrix presentation with
essentiality, irreducibility, period, and mixing conclusions. Those have
separate downstream uses and discovery intents.

### PR #1969 — numerical semigroups

| Operation | Decision | Reason |
| --- | --- | --- |
| `number_theory.numerical_semigroup.factorizations.compute` | `KEEP` | Complete bounded factorization family for one element. |
| `number_theory.numerical_semigroup.factorization_lengths.compute` | `DROP` | Projection of the factorization family. |
| `number_theory.numerical_semigroup.factorization_distance.compute` | `NATIVE_ONLY` | Direct coordinate formula. |
| `number_theory.numerical_semigroup.factorization_graph.compute` | `KEEP` | Reusable graph and component construction. |
| Element delta set, elasticity, and catenary degree | `DROP` | Deterministic projections of retained factorizations/graph. |
| `number_theory.numerical_semigroup.betti_elements.compute` | `CONTRACT_FIX` | The implementation caps a “generous” search bound at 10,000 without a completeness theorem. |
| `number_theory.numerical_semigroup.minimal_presentation.compute` | `CONTRACT_FIX` | Depends on incomplete Betti enumeration and connects every component pair rather than a minimal spanning set. |
| `number_theory.numerical_semigroup.presentation_binomials.compute` | `CONTRACT_FIX` | Uses factorization lengths as polynomial coefficients instead of the presentation's unit binomial coefficients. |
| Global delta set and catenary degree | `CONTRACT_FIX` | Depend on the unproved Betti bound and falsely imply complete global invariants. |
| `number_theory.numerical_semigroup.elasticity.compute` | `NATIVE_ONLY` | Ratio of extremal minimal generators after normalization. |

### PRs #1970–#1975

| PR | Operation | Decision |
| --- | --- | --- |
| #1970 | `transducer.subsequential.run.compute` | `KEEP` |
| #1970 | `transducer.subsequential.compose.compute` | `KEEP` |
| #1970 | `transducer.relation.path.replay.compute` | `KEEP` |
| #1970 | subsequential identity/trim and relation inverse | `NATIVE_ONLY` |
| #1971 | specialization preorder, connected components, continuity, beat points | `KEEP` |
| #1971 | closure and interior | `NATIVE_ONLY` |
| #1972 | `petri_net.fire_transition.compute` | `KEEP` |
| #1972 | enabled transitions and incidence matrix | `NATIVE_ONLY` |
| #1972 | `petri_net.reachability_graph.compute` | `CONTRACT_FIX` |
| #1973 | factor multiply, factor marginalize, d-separation | `KEEP` |
| #1973 | variable elimination | `DROP` |
| #1974 | substitution | `NATIVE_ONLY` |
| #1974 | matching and unification | `KEEP` |
| #1974 | rewrite step | `CONTRACT_FIX` |
| #1974 | normal-form iteration | `NATIVE_ONLY` |
| #1975 | tree-automaton run and accepted-tree count | `KEEP` |

## Merge boundary

No PR in this set should add its operations to the public catalog without
updating the exhaustive admission ledger. Native-only code must use an explicit
`jacobian.math` module and `__all__`. A `CONTRACT_FIX` item must include an
adversarial regression proving that incomplete search, strategy choice, or
non-uniqueness cannot be mistaken for a complete mathematical conclusion.

The frozen findings were also posted to the corresponding pull requests:
[#1965](https://github.com/morluto/jacobian/pull/1965#issuecomment-5323471295),
[#1966](https://github.com/morluto/jacobian/pull/1966#issuecomment-5323471494),
[#1967](https://github.com/morluto/jacobian/pull/1967#issuecomment-5323471673),
[#1968](https://github.com/morluto/jacobian/pull/1968#issuecomment-5323471837),
[#1969](https://github.com/morluto/jacobian/pull/1969#issuecomment-5323471989),
[#1970](https://github.com/morluto/jacobian/pull/1970#issuecomment-5323472264),
[#1971](https://github.com/morluto/jacobian/pull/1971#issuecomment-5323472482),
[#1972](https://github.com/morluto/jacobian/pull/1972#issuecomment-5323472666),
[#1973](https://github.com/morluto/jacobian/pull/1973#issuecomment-5323472887),
[#1974](https://github.com/morluto/jacobian/pull/1974#issuecomment-5323473129), and
[#1975](https://github.com/morluto/jacobian/pull/1975#issuecomment-5323473395).

## Implementation handoff

- Base tree: `61589543bbbff546edbc51d34a07887982fa4ad6` on the local
  `agent/catalog-curation` worktree.
- Installed catalog: 200 operations; SHA-256 of the sorted
  `OperationCatalogSnapshot.model_dump_json()` is
  `61ae9e1ab5c8d03e7c95df2693e3de5e327616b9d51f6b3a5f09f5b7e150151f`.
- Policy digest: not applicable. The product surface is stateless and this
  audit does not introduce a recommendation or verification-policy layer.
- Runtime: Python 3.12.13; FLINT and Z3 importable. Lean, CaDiCaL,
  `drat-trim`, Carcara, and the optional CVC5 module were absent and were not
  required by the selected gates.
- Model/prompt and raw trace: not applicable. This was a source, schema, and
  frozen-PR audit rather than a model-in-the-loop evaluation.
- Validation: `make test-math test-catalog test-cli test-tooling test-mcp`,
  `make check`, `make docs-command-check docs-linkcheck`, `make build`, and an
  installed CLI extended-GCD smoke all passed. This revision has no
  `make test-plan` target despite the repository instruction naming one.
- Open obligations: PRs #1965–#1974 require the changes recorded above before
  admission; #1975 requires removal of its unrelated stacked poset changes.
  Re-review any changed head rather than carrying forward these decisions.
