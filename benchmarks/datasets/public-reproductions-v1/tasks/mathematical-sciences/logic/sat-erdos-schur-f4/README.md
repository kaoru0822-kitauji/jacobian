# jacobian/public-reproductions-v1-sat-erdos-schur-f4

Determine the Erdos-Schur number f(4) and justify both bounds.

## Field

logic

## Provenance

- case_version: public-reproductions-v1
- contamination_class: public-answer-visible-reproduction
- fixture_digest: sha256:07fcfc8737ac90932553976a9d490205d1095f7f7cd922118e9b97ea9d79b188
- derivation: Erdos-Schur f(4)=45 agent regression; answer-visible diagnostic.

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
