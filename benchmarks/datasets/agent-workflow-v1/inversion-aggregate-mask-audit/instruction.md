# Audit a locally wrong inversion definition masked by a correct aggregate

The frozen formalization calls a pair `(i,j)` an inversion when `sigma[i] <= sigma[j]`; the intended definition uses `sigma[i] > sigma[j]`. For `n=4`, produce `/app/submission.json` following `/app/submission_schema.json` and `/app/evidence/inversion-audit.json` following `/app/evidence_schema.json`.

Supply any permutation witnessing different pointwise counts. Also report the independently computed sums of both counts over all 24 permutations and explain, through the typed complement relation, why the wrong definition nevertheless satisfies the published aggregate formula. The witness is not fixed; valid alternatives are accepted. Claim only `COMPUTED`. The verifier exhaustively recomputes both functions and both aggregates.
