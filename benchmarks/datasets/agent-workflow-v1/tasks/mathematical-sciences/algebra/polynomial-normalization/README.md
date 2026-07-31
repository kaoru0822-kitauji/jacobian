# jacobian/agent-workflow-v1-polynomial-normalization

Normalize a sparse polynomial while combining like terms.

## Field

algebra

## Provenance

- case_version: agent-workflow-v1
- contamination_class: hand-designed-structural-variant
- fixture_digest: sha256:60acd1fbcd0dc163843512d3e0fd5ad535fe21534115bf63c2e705aaa3b7df27
- derivation: Fixed sparse bivariate expression with cancellation and reordered terms.
- derivation_note: Hand-designed sparse exact expression; no symbolic backend is required at runtime.

## Contract

- schema_version: 1.4
- difficulty: medium
- maximum_assurance: VERIFIED
- agent-visible verification record schema: yes
- timeout_sec (agent): 600.0
- timeout_sec (verifier): 120.0
- environment_mode: separate

The task is self-contained and offline. The instruction names no tool,
capability, or invocation order. The verifier is a separate clean-room Python
script that scores correctness, evidence validity, scope accuracy, assurance
calibration, and aggregate reward; a wrong result or an unsupported VERIFIED
claim forces the reward to zero.
