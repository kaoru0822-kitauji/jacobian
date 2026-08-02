# Audit RSA exponent reduction over every residue class

The frozen source argues that reducing a positive RSA private exponent `d`
modulo `p-1` preserves `C^d mod p`. Its displayed manipulation introduces a
negative exponent and silently relies on `C` being invertible modulo `p`.
RSA ciphertext residues need not be units.

Submit a domain-complete repair certificate for an odd prime `p`, positive
`d` with `gcd(d,p-1)=1`, and least nonnegative remainder `d_p`.

Your certificate must:

1. diagnose why the inverse-based step is not defined for nonunits;
2. derive `1 <= d_p <= p-2` from the stated assumptions;
3. prove the unit branch without negative exponents, using
   `d=d_p+k(p-1)` with `k>=0` and Fermat's theorem;
4. prove the nonunit branch using positivity of both exponents;
5. state the exhaustive two-way domain split;
6. provide freely chosen unit and nonunit numeric witnesses satisfying the
   frozen bounds; and
7. distinguish the symbolic repair from bounded sanity checks.

The verifier independently checks the witnesses and exhaustively tests all
eligible residues for odd primes up to 43 and exponents up to 80. Those tests
are sanity evidence only; acceptance also requires the symbolic branch
certificate.

Write `/app/submission.json` and bind a concise explanation at
`/app/evidence/answer.txt` by SHA-256. Do not claim `VERIFIED`: this task does
not replay a proof assistant or certify the universal theorem beyond the
explicit certificate checker.
