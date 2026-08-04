# Certify constrained binary necklaces under dihedral symmetry

For cyclic binary words of length 16, forbid every cyclic run of three equal bits. Count equivalence classes under all rotations and reflections.

Submit a complete certificate by writing `/app/submission.json` conforming to `submission_schema.json` and a digest-bound evidence file at `/app/evidence/answer.txt`. The submission `result` object must contain:

1. `valid_labelled_words`: the total number of valid labelled words;
2. `rotation_fixed_counts`: a 16-element array where index `k` is the number of valid words fixed by rotation by `k` positions (`word[i] == word[(i+k) mod 16]`);
3. `reflection_fixed_counts`: a 16-element array where index `k` is the number of valid words fixed by the reflection through index `k` (`word[i] == word[(k-i) mod 16]`);
4. `burnside_numerator` and `orbit_count`; and
5. `canonical_representatives`: the sorted list of the lexicographically least representative of every orbit.

All count fields must be JSON integers (not booleans or floats). The evidence file `evidence/answer.txt` must be a single JSON object with exactly the keys `schema_version` (the string `"1"`), `task_id` (the task identifier), `result` (the same `result` object placed in `submission.json`), and `limitations` (the same limitations list). Bind it in `submission.json` under `evidence` with its `path` and `sha256` digest.

The verifier independently enumerates all 65,536 binary words, applies the cyclic constraint, reconstructs every dihedral action, recomputes the fixed-point table, and compares the complete orbit partition. A count without the representatives is incomplete. Claim only `COMPUTED`; this is an exact finite replay, not a proof of a general necklace theorem.
