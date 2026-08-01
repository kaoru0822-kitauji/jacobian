# Agent workflow observations

[Documentation home](../index.md)

Jacobian's fixed workflow observation surface is the Harbor
[`agent-workflow-v1`](../../benchmarks/datasets/agent-workflow-v1/README.md)
dataset. Its 26 self-contained mathematical tasks cover graph, algebra,
linear-algebra, number-theory, geometry, combinatorics, probability, and
formal-mathematics workflows, including the original graph, partition, SAT,
linear-system, Hermite, and polynomial cases.

The task bundles are agent-agnostic. Instructions describe the mathematical
outcome and evidence without naming capability IDs or prescribing
decomposition, verification order, or stopping criteria. Each task freezes its
offline input, Oracle-only solution, and separate clean-room verifier.

## Validation boundary

Task and verifier validation is separate from model observation:

```sh
make harbor-check
make harbor-oracle DATASET=agent-workflow-v1
```

The suite module resolves nested domain and field paths, renders them as
explicit Harbor task entries, and checks the generated task digests. Wrong
answers, malformed or escaped evidence, incomplete scope, and false
certification receive zero reward.

## Jacobian observation

The same task digests are used for a Jacobian-enabled observation:

```sh
export JACOBIAN_IMAGE='registry.example/jacobian@sha256:<64-lowercase-hex>'
export JACOBIAN_IMAGE_IDENTITY_FILE='/trusted/path/jacobian-image-identity.json'
export JACOBIAN_MCP_TOKEN='replace-with-at-least-32-character-token'
export JACOBIAN_AUTH_TOKENS_JSON='{"tokens":[{"tenant_id":"observation","token":"replace-with-at-least-32-character-token","scopes":["jacobian:use"]}]}'
export JACOBIAN_MODEL='your-model'
make agent-eval DATASET=agent-workflow-v1 EVAL_EXECUTE=1
```

Build repository images with `make container-image IMAGE=jacobian:local`, then
publish and digest-pin them. The target records the exact Git revision and
package version as OCI labels and refuses a dirty source tree. The trusted
release pipeline or evaluation operator must separately supply an identity
record like this one; do not derive it from the image's own labels:

```json
{
  "schema_version": "jacobian-image-identity-v1",
  "image_digest": "sha256:<64-lowercase-hex>",
  "git_revision": "<full-selected-checkout-sha>",
  "package_version": "<normalized-package-version>"
}
```

Before Harbor starts, `make agent-eval` pulls the pinned digest and requires
both that independent digest binding and matching OCI labels. A digest alone
identifies image bytes, while self-declared labels alone do not prove which
source revision those bytes contain. Preserve the external identity record
with the evaluation handoff as the provenance boundary.

Inspect Harbor ATIF together with Jacobian telemetry for discovery,
descriptions, invocation and parameter errors, artifact and verification-record
flow, repeated calls, shell activity, tokens, time, and completion. This is
workflow evidence, not a causal comparison: version 1 has no control condition,
randomized pairing, or held-out performance claim.

The separate
[`research-diagnostics-v1`](../../benchmarks/datasets/research-diagnostics-v1/README.md)
dataset is public and answer-visible. Its results remain case-level diagnostics
and must not be reported as held-out model performance.
