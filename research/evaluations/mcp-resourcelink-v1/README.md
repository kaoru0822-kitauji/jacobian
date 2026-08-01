# MCP ResourceLink pilot v1

This directory freezes the credential-free evaluation contract for issue
#195. It does not contain model traces, Harbor jobs, credentials, or a
performance claim.

The pilot has 3 server-side projection strategies, 4 case categories, and 3
repetitions: 36 paired episodes using seed 104729. The schedule is generated
by jacobian.eval.mcp_resourcelink; the JSON plan records the same identities
for external review. The case baselines are intentionally null in this
credential-free scaffold; the gate requires measured canonical structured
content digests before it can pass.

The deterministic gate checks episode binding, identical canonical structured
content across projections, agreement with the registered case baselines, no
false certification or assurance regression, task completion, exact URI
preservation on attempted reads, and at least 8 of 9 successful large-artifact
ResourceLink follow-through episodes. The model stage remains disabled until
an operator supplies model identity, credentials, runtime snapshot, and an
explicit budget authorization. A five-repetition expansion is not part of
this scaffold.

Until the pilot passes, ResourceLink remains an advisory handoff. Canonical
structured content and the URI/text fallback remain authoritative.
