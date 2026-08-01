# Core operations measurement

Runs the existing canonicalization and artifact-store microbenchmark against
the repository revision pinned in the task image. The verifier checks the raw
pyperf structure, suite identity, expected benchmark names, environment
metadata, and evidence digests. It does not compare timing values.
