# jacobian/jcb-postdoc-014

Research diagnostic: Nine-line counterexample to combinatorial determination of Jacobian-relation degree

## Field

algebraic-geometry

## Provenance

- case_version: research-diagnostics-v1
- contamination_class: public-answer-visible-diagnostic
- fixture_digest: sha256:347a759aaea2891bf4b633598a1fde7b2635c1a15569f59fc31659eab4d4e47a
- derivation: Two rational arrangements of nine projective lines have isomorphic intersection lattices but different minimal degrees of Jacobian relations. The decisive computation is an exact graded-kernel calculation, close to Jacobian's polynomial and rational-linear portfolio but not currently exposed as one domain-owned operation.

## Portfolio status

- historical_fit: `MISSING`
- current_status: `COVERED`
- evaluation_status: `REGRESSION_COVERED`
- next_action: Run repeated public model reproductions under the frozen no-retrieval profile; the v1 MISSING label remains historical and must not be edited.

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
