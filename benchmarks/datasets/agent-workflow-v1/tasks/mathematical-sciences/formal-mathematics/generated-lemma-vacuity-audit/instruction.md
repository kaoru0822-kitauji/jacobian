# Audit two generated proof lemmas

The frozen input contains two generated intermediate lemmas attached to IMO
problems. Determine whether each lemma makes non-vacuous progress toward its
stated intent.

For the square-bound lemma:

1. give an in-range pair of distinct cards and an existential witness that
   satisfies the frozen implication only because its antecedent is false;
2. reconstruct the intended universal square-witness contract using the
   supplied logical-AST vocabulary; and
3. give a separate in-range square-sum instance on which that corrected
   contract has a true antecedent and valid bounds.

For the common-divisor lemma, give positive unequal integers and `d = 1` that
satisfy all three divisibility conclusions while the original theorem premise
is false. Explain why this proves premise-independence of the generated lemma,
not falsity of the original IMO theorem.

Write `submission.json` to the exact agent-visible schema. Put a concise audit
in `evidence/answer.txt`, include one `RESULT_JSON:` line containing the exact
submitted result as compact JSON, and bind that file with its SHA-256 digest.
Do not claim Lean compilation or theorem verification; neither is performed.
