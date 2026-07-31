# jacobian/agent-workflow-v1-graph-artifact-composition

Compose a graph distance artifact with a maximum-degree vertex set.

## Field

graph-theory

## Provenance

- case_version: agent-workflow-v1
- contamination_class: hand-designed-structural-variant
- fixture_digest: sha256:afc9c57132594b60e9d309377efd0866109303fc5639d93b8f0ad6b081313e65
- derivation: Fixed connected six-vertex graph with a non-singleton distance calculation.
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
