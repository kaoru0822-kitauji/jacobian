# Audit a finite calendar claim

Audit the claim in the offline input by exhaustively checking the declared
finite date range. Return the truth value, exact count, and every qualifying
date in calendar order, including each concatenated integer.

Write `submission.json` to the exact agent-visible `submission_schema.json`.
Put a concise description of the exhaustive check in `evidence/answer.txt`,
include a `RESULT_JSON:` line containing the submitted result as JSON, and bind
the file with its SHA-256 digest.
