# Normalized bivariate Jacobian degree-(2,3) infeasibility

Work over `QQ`.  The frozen input specifies the affine-normalized map

`P=x+a20*x^2+a11*x*y+a02*y^2`

and

`Q=y+b20*x^2+b11*x*y+b02*y^2+b30*x^3+b21*x^2*y+b12*x*y^2+b03*y^3`.

The constant-Jacobian equations are the nine nonconstant coefficients of
`det J(P,Q)-1`.  Exact component degrees mean that the quadratic coefficient
vector of `P` and the cubic coefficient vector of `Q` are both nonzero.  Use
the complete 3 by 4 chart cover from the input: chart `(a_i,b_j)` adds one
Rabinowitsch variable and equation `t*a_i*b_j-1=0`.

Establish that every chart is infeasible by supplying exact rational
Nullstellensatz multipliers satisfying `sum(h_i*f_i)=1` in each chart.  Write
the complete structural evidence to
`evidence/nullstellensatz-certificate.json` using the agent-visible
`certificate_schema.json`, then bind that file by SHA-256 in `submission.json`.

This is a public answer-visible diagnostic.  Claim `COMPUTED`, not `VERIFIED`:
the clean-room benchmark verifier independently replays the identities, but is
not product verification authority.  A failed search, a Gröbner status, or a
prose proof without all 12 identities is not a conclusion.
