# Eliminate a complex power-sum system

Solve the frozen complex-number problem completely. Introduce symmetric
variables and a power-sum recurrence, then provide an exact certificate that:

1. derives the polynomial relation for the two possible values of `s=x+y`;
2. records the exact power-sum polynomials through `A_6`;
3. proves every denominator used in the two hypotheses and target is nonzero;
4. returns both and only the possible target values as quadratic surds; and
5. certifies achievability by reconstructing `x,y` as the two complex roots
   of a quadratic with the submitted sum and product.

The two algebraic branches may appear in either order. Rational numbers must be
reduced with positive denominators. Write the result to
`/app/submission.json`, place a concise derivation in
`/app/evidence/answer.txt`, and bind the evidence by SHA-256.

Do not claim `VERIFIED`: the clean-room checker replays exact polynomial and
quadratic-field arithmetic, but no external proof assistant checks the general
complex-algebra argument.
