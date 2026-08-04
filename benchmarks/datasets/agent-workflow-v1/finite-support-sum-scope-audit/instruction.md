# Audit the summation domain

For fixed `n`, the source defines `a_n` by summing over every binary function
on the positive integers with finite support, then silently replaces that set
by subsets of `{1,...,n}`.

Choose `4 <= n <= 12` and provide at least six distinct singleton supports
strictly beyond `n`. Compute each summand and the resulting finite partial-sum
lower bound. Then repair the definition by restricting supports to
`{1,...,n}`: provide at least three exact rational checkpoints for

`c_n = product_{k=1}^n (2+1/k^2) / n!`

and a uniform ratio certificate showing `c_{n+1}/c_n <= 3/4` for every `n>=2`.
Bind an evidence object at `evidence/scope-audit.json`. The object must have exactly `schema_version`, `task_id`, `result`, and `limitations`; use `schema_version: "1"`, task ID `jacobian/finite-support-sum-scope-audit`, and exact copies of the submitted `result` and `limitations`. Assurance is `COMPUTED` only.
