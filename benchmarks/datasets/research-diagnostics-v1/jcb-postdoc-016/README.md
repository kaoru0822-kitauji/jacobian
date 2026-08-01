# jacobian/jcb-postdoc-016

Research diagnostic: Erdős Problem 364: kernel-checked finite range versus an unbounded powerful-number conjecture

## Field

computational-number-theory

## Provenance

- case_version: research-diagnostics-v1
- contamination_class: public-answer-visible-diagnostic
- fixture_digest: sha256:38d8999a446d7da5d3cd9b60ba7876389bf0c291c3ab9e507b19df020c89f301
- derivation: The conjecture that three consecutive powerful numbers do not exist remains open, while a separate artifact kernel-checks the finite range through 10^14. This is an unusually clean test of bounded-certificate ingestion, exact scope, and resistance to promoting massive finite verification into an unbounded theorem.

## Portfolio status

- historical_fit: `MISSING`
- current_status: `OPEN_GAP`
- evaluation_status: `BLOCKED_ON_INTERVENTION`
- next_action: Implement and independently check the atomic powerful-number predicate first; keep the 10^14 chunk replay as a separate provider- and format-bound candidate.

## Contract

- schema_version: 1.4
- difficulty: hard
- maximum_assurance: COMPUTED
- agent-visible verification record schema: no
- timeout_sec (agent): 600.0
- timeout_sec (verifier): 120.0
- environment_mode: separate

The task is self-contained and offline. The instruction names no tool,
capability, or invocation order. The verifier is a separate clean-room Python
script that scores correctness, evidence validity, scope accuracy, assurance
calibration, and aggregate reward; a wrong result or an unsupported VERIFIED
claim forces the reward to zero.
