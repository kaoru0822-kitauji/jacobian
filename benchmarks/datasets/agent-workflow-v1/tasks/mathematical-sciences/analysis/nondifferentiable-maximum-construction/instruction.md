# Construct a nondifferentiable maximum

Construct a continuous piecewise-linear function on `[-1,1]` whose maximum is
attained at `0` but which is not differentiable there. Use the two-branch family
declared in the input and choose any rational peak and slopes satisfying the
requirements.

Return exact rational parameters and the branch values at the join. The
verifier independently checks continuity at zero, monotonicity toward and away
from the peak, and the unequal one-sided derivatives. Write `submission.json`
to the exact `submission_schema.json` contract, put a concise derivation in
`evidence/answer.txt`, and bind that file with its SHA-256 digest.
