# Repair a natural-subtraction proof

Audit the failed rewrite in the frozen natural-number proof branch, then give
an exact algebraic repair certificate.

First report whether the failed pattern occurs as a subtree of the target AST.
Then use the declared equation basis to derive the goal: submit one rational
multiplier per basis equation and the resulting coefficient vector in the
declared variable order. The subtraction-recovery equation is justified only
by the recorded `b<=a` side condition.

The verifier independently traverses the expression tree and recomputes the
linear combination over exact rationals. It does not run Lean or accept a
`VERIFIED` claim. Write `submission.json` to `submission_schema.json`, put a
concise diagnosis and derivation in `evidence/answer.txt`, and bind its SHA-256
digest.
