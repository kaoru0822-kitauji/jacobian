# SAT decision with witness

Decide the exact CNF formula in `input.json`. For a satisfiable formula, return
`SATISFIABLE` and a complete Boolean assignment that satisfies every clause.
For an unsatisfiable formula, return `UNSATISFIABLE` only with the evidence
appropriate to that conclusion. Record the clause-by-clause check in
`evidence/answer.txt`, include its SHA-256 digest, and write `submission.json`
to the exact agent-visible `submission_schema.json`. Claim `VERIFIED` only when
you also provide the independently bound verification record required by the
schema; otherwise claim `COMPUTED`. The record file must contain the complete
operator-authorized verification record, including its schema version, checker
identity and digest, evidence kind and URI, bindings, conclusion, arithmetic,
method, coverage, request digest, and environment digest. It must bind the
exact input, assignment, conclusion, and scope.
