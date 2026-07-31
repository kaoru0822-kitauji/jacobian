# Audit an expectation claim

Audit the claim in the offline input using exact arithmetic. Account explicitly
for the dependence in `f(f(x))` when `f(x)=x`; return the relevant exact point
probabilities, the ordered squared-difference sum, and the exact expectation.

Write `submission.json` to the exact agent-visible `submission_schema.json`.
Put a concise exact derivation in `evidence/answer.txt`, include a
`RESULT_JSON:` line containing the submitted result as JSON, and bind the file
with its SHA-256 digest.
