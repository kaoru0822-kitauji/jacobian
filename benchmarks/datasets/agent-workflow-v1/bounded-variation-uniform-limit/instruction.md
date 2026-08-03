# Separate uniform convergence from variation convergence

On `[0,2*pi]`, choose an integer `q` with `2 <= q <= 9` and use

`f_n(x) = sin(q*n*x)/(q*n)`, for `n >= 1`.

Submit a certificate that `f_n` converges uniformly to zero while every
`f_n` has total variation exactly four. State the general sup-norm bound and
the exact monotone-segment accounting: two endpoint segments and all interior
segments. Include at least four distinct freely chosen positive indices with
their frequency, amplitude, segment counts, endpoint contribution, interior
contribution, and total variation.

The verifier recomputes every integer and rational identity. Sampling, a graph,
or a conclusion label alone is insufficient. Evidence must contain exactly one
`RESULT_JSON:` line equal to `result` and explain why uniform convergence alone
does not force convergence of total variation. Do not claim proof-assistant
verification.
