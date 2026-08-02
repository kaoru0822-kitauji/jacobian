# Seven-vertex graph-class enumeration

Enumerate every isomorphism class of simple graphs on exactly seven vertices
that is connected, triangle-free, non-bipartite, and has minimum degree at
least two. Return the total class count and one labelled representative of
each class. Representatives must use vertices `0` through `6`.

Write `submission.json` to the exact agent-visible `submission_schema.json`.
Write `evidence/enumeration-certificate.json` as a JSON object with exactly
`schema_version`, `task_id`, `result`, and `limitations`. Use schema version
`"1"` and copy the other values exactly from the submission, then bind the
certificate by SHA-256. Use limitation code `ORDER_SEVEN_SCOPE_ONLY`.
