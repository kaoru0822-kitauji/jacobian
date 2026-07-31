# ADR 0009: Keep bounded LRAT replay experimental

Status: Accepted, pre-stable

## Decision

Jacobian keeps `sat.lrat.verify` as an explicitly bounded experimental checker.
Its v1 dialect is `jacobian.lrat.rup/v1`: ASCII proof bytes containing clause
additions with positive ordered RUP hints, followed by the empty clause. RAT
hints, clause deletions, alternate encodings, and parser extensions are
unsupported and fail closed. The checker binds the exact CNF, proof bytes,
limits, parser/checker identity, and provider runtime before replay.

The current handwritten replay is verification-only; Jacobian does not claim to
produce LRAT certificates. A `VERIFIED` result remains available only through
the operator-authorized independent checker path and is limited to this exact
dialect and scope.

## Authority gate

A broader stable LRAT checker may be authorized only after a maintained backend
is selected through a recorded comparison of independent implementation,
supported dialect, deterministic replay, invalid-proof rejection, bounded
resources, reproducible release and artifact identity, license, and operation
without Jacobian's SAT producer. The candidates to evaluate are the current
bounded checker, CakeLPR, and an available pinned Lean LRAT checker. Until one
candidate passes every gate, no broader LRAT authority is implied.

The required corpus includes valid proofs, malformed and truncated proofs,
wrong-CNF bindings, altered hints, unsupported steps, and resource-limit
failures. Rejection or an unavailable backend remains `UNKNOWN` and creates no
verification record.
