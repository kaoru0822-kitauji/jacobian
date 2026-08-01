# jacobian/jcb-postdoc-004

Research diagnostic: Written on the Wall II Conjecture 194: discover an 18-vertex obstruction

## Field

extremal-graph-theory

## Provenance

- case_version: research-diagnostics-v1
- contamination_class: public-answer-visible-diagnostic
- fixture_digest: sha256:b321914443aa1cdcb43a232065773645a7a945bf2b556575cb9d407796fdf643
- derivation: Unlike the supplied-witness closure cases, this task asks the agent to discover a compact structured counterexample while using exact graph invariants to guide and check the search.

## Portfolio status

- historical_fit: `PARTIAL`
- current_status: `PARTIAL`
- evaluation_status: `RUNNABLE_PUBLIC_REPRODUCTION`
- next_action: Run the unchanged public prompt to inspect composition and discovery; do not add an opaque counterexample-search workflow.

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
