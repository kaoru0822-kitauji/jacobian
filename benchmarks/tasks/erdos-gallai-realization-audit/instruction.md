# Audit two degree-sequence claims

For each sorted sequence in `/app/input.json`, determine whether it is the
degree sequence of a finite simple undirected graph. For the graphical case,
submit any simple edge list whose exact degrees match the sequence. Edge pairs
may be oriented either way, and vertex labels may be zero-based (`0..n-1`) or
one-based (`1..n`). For the
nongraphical case, submit every violating Erdős–Gallai index `k`, with the
exact left and right sides of the inequality.

Bind a concise explanation at `/app/evidence/answer.txt` and write
`/app/submission.json`. Do not claim completeness beyond these two frozen
sequences or claim `VERIFIED`; the checker provides exact finite computation.
