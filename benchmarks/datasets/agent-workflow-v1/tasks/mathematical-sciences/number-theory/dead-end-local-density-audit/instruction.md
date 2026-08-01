# Audit local density factors for square-free digit walks

For a prime `p`, base `b >= 2`, and digit set `T`, define the forbidden residue
set modulo `p^2` by

`F = {r : p^2 divides r or p^2 divides b*r+d for some d in T}`.

The local density factor is `(p^2-|F|)/p^2`.

Audit every frozen case in `/app/input.json`. For each case, classify the
arithmetic branch as `INVERTIBLE`, `SINGLY_DIVISIBLE`, or `SQUARE_DIVISIBLE`;
submit the complete sorted set of forbidden residues, the valid residue count,
and the density as a reduced numerator and denominator. Your concise evidence
must explain why the three divisibility branches require different reasoning
and must identify any collision or vacuous digit condition present in the
cases.

Write `/app/submission.json` and bind `/app/evidence/answer.txt` by SHA-256.
Do not claim that the global density formula, Euler-product convergence, or the
upstream Lean development has been verified. The checker establishes only the
four finite local computations and therefore permits at most `COMPUTED`.
