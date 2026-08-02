# Indexed pairwise vacuity audit

This Assurance benchmark freezes the `Set.range` quantification defect reported in google-deepmind/formal-conjectures issue #4045 against source commit `71d34fc2958f1010ee43ccd4d54a9631574d7ef9`.

The agent must construct a nontrivial exact coset covering of a cyclic group whose repeated part value is deduplicated by `Set.range`. The verifier reconstructs the subgroup, every coset, exact-cover conditions, value-range pairwise predicate, and indexwise predicate. Alternative groups satisfying the frozen bounds are accepted.

Difficulty is **Hard (provisional)** because the certificate combines finite-group construction, exact-cover completeness, and a higher-order quantifier audit. This does not prove or disprove Erdős problem 274.

