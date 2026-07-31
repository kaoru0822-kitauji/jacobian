# jacobian/agent-workflow-v1-polynomial-map-collision

Verify a collision in a polynomial map using an explicit witness.

## Field

algebra

## Provenance

- case_version: agent-workflow-v1
- contamination_class: hand-designed-structural-variant
- fixture_digest: sha256:9206bd2581f20ceabd16a483ffe98eff97cfcd402f84f7866fdc257c704aa8d3
- derivation: Fixed symmetric map and two distinct integer points with equal images.
- derivation_note: Hand-designed symmetric polynomial map; no external source is loaded at runtime.

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
