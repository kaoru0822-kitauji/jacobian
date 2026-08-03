# Repair a Metric TSP proof

Audit and repair the flawed claim in the offline input. Identify the invalid
inference and state the strongest generic guarantee supported by the
double-tree argument. For the supplied metric, give a minimum spanning tree,
an Euler circuit of its doubled edges, the Hamiltonian cycle obtained by
retaining first visits, and an optimal Hamiltonian cycle. Report all exact
weights so the concrete trace demonstrates why exactness is unsupported while
the repaired guarantee holds.

Represent the repaired generic claim through the structured shortcut-cost
relation and approximation-factor fields in `submission_schema.json`. Write
`submission.json` to that exact schema. Write `evidence/certificate.json` with
exactly `schema_version`, `task_id`, `result`, and `limitations`, matching the
submission, and bind the file with its SHA-256 digest.
