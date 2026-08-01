# LRAT authority feasibility record

Status: evaluation incomplete; no production checker authority changed.

Jacobian's public proof profile remains `jacobian.lrat.rup/v1`: canonical ASCII
clause additions with positive RUP hints, ending at the empty clause. The
maintained authority candidate is the repository-pinned Lean 4.31 checker and
its independent `check_sound` boundary. The existing handwritten replay stays
experimental until that candidate passes every gate.

## Lean-only authority path

The Lean adapter must bind the exact CNF, proof bytes, limits, checker identity,
Lean toolchain/runtime identity, and source/build digest. It must reject
anything outside the frozen addition-only RUP profile and translate only the
documented successful checker result into verification evidence. Timeout,
malformed output, unavailable Lean, runtime drift, and incomplete replay are
non-conclusions.

The reproducible profile corpus is frozen at
`research/evaluations/lrat-authority-v1/corpus.json`; its recorded SHA-256 is
`sha256:7af048de3c3f2eb9481c13d03663b280a39a0c124c55b87b0b31c42b139a1f26`.
The checker-binding regression lane exercises wrong-CNF, proof-byte, lineage,
and expected-binding mutations directly against the current experimental
checker.

## Required evidence

The authority handoff must include the exact pinned Lean 4.31 runtime and
source/build identity, differential agreement over the frozen valid corpus,
rejection of clause, mapping, hint, digest, truncation, deletion, RAT,
encoding, and malformed-output mutations, bounded time/memory/stack/proof-size
behavior, strict success parsing, runtime-drift rejection, and independent
review of the adapter.

No CakeLPR or CakeML runtime is registered or used by Jacobian. They are
deliberately excluded from this authority path so the project does not add a
second generated-checker build and provenance boundary.

The incomplete handoff is recorded at
`research/evaluations/lrat-authority-v1/handoff.yaml`. Until Lean passes the
gates and an operator authorizes its runtime, `sat.lrat.verify` remains the
existing bounded experimental capability and its handwritten replay must not
be broadened.
