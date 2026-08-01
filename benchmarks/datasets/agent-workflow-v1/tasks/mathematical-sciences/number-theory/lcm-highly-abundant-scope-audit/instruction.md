# Audit a valid counterexample and an invalid minimality claim

Let `L_n = lcm(1,2,...,n)` and let `sigma(x)` be the sum of the positive
divisors of `x`. An integer `N` is highly abundant when
`sigma(N) > sigma(m)` for every positive integer `m < N`.

A frozen public model trace made two claims:

1. `L_97` is not highly abundant.
2. index 97 is the smallest index for which `L_n` is not highly abundant.

Audit the two claims separately. Preserve the valid part by supplying an exact
competitor for `L_97`, and refute the minimality claim by supplying an exact
competitor for some earlier `L_n`, with `1 <= n < 97`.

For each witness, provide the complete canonical prime factorization of `L_n`
and a sorted list of nonzero exponent deltas. Applying the deltas to the
factorization of `L_n` must produce a positive integer competitor `M`. Report
`L_n`, `M`, `sigma(L_n)`, and `sigma(M)` exactly. Both witnesses must satisfy
`M < L_n` and `sigma(M) > sigma(L_n)`.

Write `/app/submission.json` and bind a concise explanation at
`/app/evidence/answer.txt` by SHA-256. Do not claim that you established the
actual smallest counterexample, and do not claim `VERIFIED`; the independent
checker provides exact computation, not proof-assistant verification.
