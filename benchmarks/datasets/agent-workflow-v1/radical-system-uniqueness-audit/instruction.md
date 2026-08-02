# Audit a radical system and certify its unique real solution

The frozen input contains a real system involving square, cube, and fourth
roots, together with a claim that it has at least two solutions. Determine the
actual real solution set and audit that claim.

Submit a certificate that introduces `u = b^(1/6)`, derives the exact
univariate elimination polynomial, factors it completely, classifies every
real root against the principal-root domain constraints, reconstructs every
surviving `(a,b,c)` triple, and checks all three original equations exactly.
Your evidence must explain why rejected algebraic roots cannot represent real
solutions. Write `submission.json` according to `submission_schema.json` and
bind `evidence/answer.txt` by SHA-256.

This task has no external proof-assistant replay, so claim at most `COMPUTED`.
