# Euler fourth-power claim scope audit

Refute the frozen universal claim by supplying a primitive positive-integer witness
`x^4 + y^4 + z^4 = w^4` within the declared bound. The three left bases must be
strictly increasing, all four bases must be distinct, and their joint gcd must be one.

Submit the exact fourth powers, both sides of the equality, and residue checks for
every required modulus. Explain why this single witness refutes exactly the frozen
claim, while establishing neither minimality nor any statement about other exponents
or numbers of summands.

The verifier accepts any witness satisfying this contract; it does not compare against
one memorized tuple. Claim at most `COMPUTED`. Write `/app/submission.json` and bind
`/app/evidence/answer.txt` by SHA-256.
