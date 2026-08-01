# Audit shallow Lean axiom reports

The frozen input contains two declaration-dependency graphs and the axiom sets
reported by the affected Lean collector. For each case, reconstruct the full
transitive dependency closure from the declared roots, compare it with the
observed report, and list the missing dependencies in sorted order.

Classify each report as `COMPLETE` or `INCOMPLETE`. Classify every missing
dependency by its frozen role. Bind a concise explanation at
`/app/evidence/answer.txt` and write `/app/submission.json`.

Do not claim proposition truth, current Lean behavior, or independent
reproduction of the upstream issue. The checker audits only the frozen graphs
and permits at most `COMPUTED`.
