# Startup phase measurements

Runs the existing storage, schema, materialization, assembly, attachment, and
hydration phase benchmarks against the pinned revision. The verifier checks the raw
pyperf structure, suite identity, expected benchmark names, environment
metadata, and evidence digests. It does not compare timing values.
