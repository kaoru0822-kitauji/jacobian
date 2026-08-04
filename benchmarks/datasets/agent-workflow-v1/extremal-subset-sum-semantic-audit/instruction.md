# Audit an extremal subset-sum formalization

Compare the frozen informal requirement with the proposed Lean declaration.
Determine whether the declaration faithfully preserves the fixed outer
parameter and the requirement that no subset of a candidate sums to the target.

Supply two exact certificates:

1. two cutoff multipliers for the same target whose legacy extrema disagree,
   showing that the shadowed universal binder makes one function value satisfy
   incompatible equations;
2. the exact legacy and intended extrema on the frozen finite universe,
   including a legacy-optimal candidate, an intended-optimal candidate, and a
   subset that invalidates the legacy candidate under the intended predicate.

The legacy predicate checks only the sum of the whole candidate. The intended
predicate checks every subset, including the empty subset and the candidate
itself. Use lists as mathematical sets: entries must be strictly increasing.

Do not claim that Lean parsing, elaboration, compilation, or the corrected
asymptotic conjecture has been verified. Write `submission.json` to the exact
agent-visible `submission_schema.json`. Put a concise audit in
`evidence/answer.txt`, include a `RESULT_JSON:` line containing the submitted
result as JSON, and bind that file with its SHA-256 digest.
