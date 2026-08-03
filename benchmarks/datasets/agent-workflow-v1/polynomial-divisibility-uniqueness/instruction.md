Determine every integer parameter `a` for which

`x^2 - x + a` divides `x^13 + x + 90` in `Z[x]`.

Write `/app/submission.json` using `/app/submission_schema.json`. Coefficient arrays are ascending. Your certificate must give the two coefficient polynomials of the remainder in `Q[a][x]`, their monic gcd in `Q[a]`, the unique parameter, and the exact integer quotient at that parameter. The gcd is what establishes completeness over all integers; checking only the reported parameter is insufficient.

Write `/app/evidence/divisibility-certificate.json` as a JSON object with exactly `schema_version`, `task_id`, `result`, and `limitations`. Use schema version `"1"` and copy the other three values exactly from the submission. Report the limitation code `FROZEN_POLYNOMIAL_FAMILY_ONLY`.

Report `COMPUTED`, not `VERIFIED`. The verifier independently reconstructs the symbolic remainder, polynomial gcd, and product identity.
