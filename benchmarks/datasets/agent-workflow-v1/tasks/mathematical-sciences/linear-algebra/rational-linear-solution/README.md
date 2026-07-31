# jacobian/agent-workflow-v1-rational-linear-solution

Solve an exact rational linear system.

## Field

linear-algebra

## Provenance

- case_version: agent-workflow-v1
- contamination_class: hand-designed-structural-variant
- fixture_digest: sha256:a24aaad769323b66fa1a0f91d757fc84f6cedeff3dd10ba37c8b15b9d975a3ba
- derivation: Fixed two-variable system with a non-integral unique solution.
- derivation_note: Hand-designed exact system; no floating-point arithmetic is needed.

## Contract

- schema_version: 1.4
- difficulty: medium
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
