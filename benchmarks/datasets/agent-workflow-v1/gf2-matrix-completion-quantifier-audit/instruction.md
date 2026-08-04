# Audit a minimum-rank completion argument

The frozen proof makes two claims:

1. support in `|i-j|<3` makes the pattern symmetric; and
2. because zero positions are free, choosing a full-rank submatrix forces a
   lower bound on the minimum completion rank.

Submit an exact GF(2) certificate that refutes both steps. Choose a dimension
from 8 through 14, give an asymmetric binary 3-pattern with at least `n+1`
forced ones, and provide two complete binary matrices satisfying `A ∘ M = M`:
one of rank exactly 1 and one of rank exactly `n`.

Write the certificate to `/app/submission.json` and bind an evidence copy at
`evidence/matrix-completion.json`. The evidence file must be a JSON object with
exactly the fields `schema_version` (the string `"1"`), `task_id`
(`"jacobian/gf2-matrix-completion-quantifier-audit"`), `result` (the same
`result` object placed in the submission), and `limitations` (the same
`limitations` array placed in the submission). It is not the full submission
envelope. Assurance is capped at `COMPUTED`.
