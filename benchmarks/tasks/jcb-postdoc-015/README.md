# jacobian/jcb-postdoc-015

Research diagnostic: Erdős Problem 707: a Sidon set forbidden in every finite perfect difference set

## Field

additive-combinatorics

## Provenance

- case_version: research-diagnostics-v1
- contamination_class: public-answer-visible-diagnostic
- fixture_digest: sha256:8445cbf54afc420565219be7b70803de16d208c3422a096bec5374b89a231ef8
- derivation: The conjecture that every finite Sidon set extends to a finite perfect difference set was a long-standing Erdős prize problem. The five-element Mian-Chowla prefix is a counterexample, with a reproducible Lean artifact, but Jacobian currently has only low-level finite-set and modular primitives rather than the required design-theoretic obstruction.

## Portfolio status

- historical_fit: `MISSING`
- current_status: `OPEN_GAP`
- evaluation_status: `BLOCKED_ON_INTERVENTION`
- next_action: Return to workflow discovery before proposing a broad perfect-difference-set contract.

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
