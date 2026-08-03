# Repair and replay a Metamath-style proof

The frozen input contains a small Metamath-style assertion registry, atomic
hypotheses, and a corrupted reverse-Polish proof of the implication
syllogism. Repair the trace with exactly two token replacements and submit the
complete repaired proof.

For every proof token, record the stack depth and top expression after the
token is applied. For assertion tokens, also record the exact variable
substitution inferred from their ordered hypotheses. Atomic tokens have an
empty substitution. Expressions are token arrays and must match the frozen
syntax exactly.

The proof checker pops ordered hypotheses, unifies every pattern variable
consistently, instantiates the conclusion, and requires one final stack item
equal to the target. Merely naming the two repaired labels or asserting the
target is insufficient.

Write `submission.json` to the provided schema. Write `evidence/answer.txt`
with a nonempty explanation and one line beginning `RESULT_JSON:` followed by
the exact compact JSON serialization of `result`. Digest-bind that file and
claim at most `COMPUTED`.
