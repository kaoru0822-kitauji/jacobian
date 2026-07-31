# Polynomial-map collision verification

Verify or refute the supplied collision claim for the exact polynomial map and
two points in `input.json`. Return the evaluated image of each point and state
`TRUE` only when the points are distinct and their images are equal. Show both
evaluations in `evidence/answer.txt`, include its SHA-256 digest, and write
`submission.json` to the exact agent-visible `submission_schema.json`.
Claim `VERIFIED` only by writing
`evidence/verification-record.json` and binding it through the
submission descriptor's `verification_record_uri`; otherwise claim `COMPUTED`.
