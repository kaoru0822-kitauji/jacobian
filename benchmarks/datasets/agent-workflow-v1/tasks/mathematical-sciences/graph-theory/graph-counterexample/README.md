# jacobian/agent-workflow-v1-graph-counterexample

Find and document a counterexample to a finite graph claim.

## Field

graph-theory

## Provenance

- case_version: agent-workflow-v1
- contamination_class: hand-designed-structural-variant
- fixture_digest: sha256:5e334b8b22312e495bcf8fd9f94bc288d8d39e84a9e1384eecd74a7ecb3ed0ac
- derivation: A fixed six-vertex triangle-free graph with an odd cycle and minimum degree two.
- derivation_note: Hand-designed finite graph; no external source is loaded at runtime.

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
