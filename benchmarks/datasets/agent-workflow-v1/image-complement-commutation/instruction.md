# Classify direct-image/complement commutation

For each frozen finite mapping, determine whether `f(S \ X) = T \ f(X)` for every subset `X` of the domain. Classify the mapping as `BIJECTIVE`, `INJECTIVE_NOT_SURJECTIVE`, or `SURJECTIVE_NOT_INJECTIVE`; report the complete number of subsets checked; and, when commutation fails, give the first failing subset in increasing bitmask order together with both unequal sides. For a commuting case, all three failure fields must be null.

Claim only `COMPUTED`. The verifier exhaustively replays the powerset semantics; sampled subsets are incomplete.
