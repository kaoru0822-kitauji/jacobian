# Hermite normal form

Compute the row Hermite normal form of the exact integer matrix in `input.json`.
Return the normal form and an integer transformation `U` satisfying `U A = H`
with determinant ±1. Include the row operations or a certificate in
`evidence/answer.txt`, include its SHA-256 digest, and write `submission.json`
to the exact agent-visible `submission_schema.json`.
Claim `VERIFIED` only with the exact independently bound verification record
from the schema; otherwise claim `COMPUTED`.
