# jacobian/jcb-postdoc-019

Research diagnostic: normalized bivariate Jacobian degree-(2,3) infeasibility.

## Field

algebraic-geometry / computational-commutative-algebra

## Provenance

- case_version: research-diagnostics-v1
- contamination_class: public-answer-visible-diagnostic
- fixture_digest: sha256:99fdb8056b95863414f40c670e37e6a3cf5d487e8b8ff930837b9a22f5e88021
- derivation: the exact degree disjunction is split into 12 Rabinowitsch charts, each certified by a bounded rational Nullstellensatz identity.

## Portfolio status

- historical_fit: `MISSING`
- current_status: `COVERED_WHEN_SINGULAR_AVAILABLE`
- evaluation_status: `PUBLIC_REPRODUCTION`
- next_action: run repeated Jacobian-on/off trials only after freezing protected coefficient, chart, and mutation variants outside this public dataset.

## Contract

- schema_version: 1.4
- difficulty: hard
- maximum_assurance: COMPUTED
- timeout_sec (agent): 900.0
- timeout_sec (verifier): 120.0
- environment_mode: separate

The verifier is standard-library-only.  It reconstructs the frozen generators,
checks exact variable and chart coverage, and multiplies every submitted sparse
QQ polynomial.  It does not score prose keywords or trust producer metadata.
