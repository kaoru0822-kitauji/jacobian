# Audit the squarefree-class argument

Prove the frozen universal claim by connecting three layers rather than by constructing one example set:

1. classify positive integers by their squarefree kernel and establish exactly when a product is a square;
2. translate the ordered-pair count into a sum of squares of class sizes and an independent transversal into distinct classes;
3. give a complete modular certificate showing that `2023` cannot be a sum of at most three integer squares.

You may choose any modulus within the frozen bounds. Submit its complete, sorted set of quadratic residues and the exact target residue. The verifier will independently enumerate all zero-, one-, two-, and three-square residue sums; checking only selected decompositions is insufficient.

Write `/app/submission.json` matching the supplied schema. Do not claim machine verification or a classification beyond the frozen theorem. Report the limitation code `SQUAREFREE_KERNEL_LEMMA_NOT_FORMALLY_CHECKED`.

Write `/app/evidence/independence-certificate.json` as a JSON object with exactly `schema_version`, `task_id`, `result`, and `limitations`. Use schema version `"1"` and copy the other three values exactly from the submission, so the certificate is unambiguously bound to it.
