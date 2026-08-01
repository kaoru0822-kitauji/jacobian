# MCP ResourceLink evaluation

Jacobian keeps the durable structured result authoritative while evaluating
three server-side projection strategies:

- `FULL_INLINE`: the complete canonical result is included in text content;
- `COMPACT_URI_TEXT`: bounded text includes the recoverable URI projection;
- `COMPACT_URI_TEXT_RESOURCE_LINK`: the same compact text is accompanied by an
  additive MCP `ResourceLink`.

These names are composition and evaluation seams only. They are not agent-facing
arguments, public tools, or compatibility modes. Every invocation continues to
return canonical structured content, and a link is never the sole carrier of
scope, assurance, or a mathematical conclusion.

The frozen pilot uses scalar, graph/distance, countermodel/table, and
certificate/verification cases; seed `104729`; three repetitions per case; and
identical model, prompt, budget, runtime snapshot, and randomized ordering. The
pilot has 36 episodes. It requires zero false certification, no scope or
assurance regression, correct task completion, exact URI preservation on read
attempts, and at least 8 of 9 successful large-artifact follow-through episodes.
The final five-repetition comparison requires a separate operator budget
authorization and is not run by this change.

Transcript telemetry records links returned, exact `resources/read` attempts,
URI and artifact-digest preservation, successful reads, unnecessary reads, MCP
wire bytes, model-visible bytes, and tool calls. Direct MCP tests cover exact
retrieval, tenant/authentication isolation, missing resources, digest mismatch,
and read-only behavior. Until the pilot is authorized and passes, links remain
advisory and URI/text plus canonical structured content remain authoritative.

The credential-free schedule and fail-closed gate are frozen in
`research/evaluations/mcp-resourcelink-v1/` and exposed through
`jacobian.eval.mcp_resourcelink`. That harness validates supplied episode
evidence; it does not run a model or create a performance claim. The four
case directories contain domain-validated input bundles and explicit
`UNMEASURED` digest records. The gate will not pass until a frozen runtime
snapshot supplies those canonical-content baselines. Normalized one-record-
per-episode JSONL can be exchanged with
`write_resource_link_observations` and `read_resource_link_observations`.
