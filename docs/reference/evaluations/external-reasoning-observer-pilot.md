# External reasoning observer pilot

[External reasoning observer](external-reasoning-observer.md) · [Evaluation references](index.md)

- Status: completed exploratory pilot
- Date: 2026-08-09 (America/Los_Angeles)
- Frozen study: `external-reasoning-observer-v1`
- Evidence class: paired post-run workflow observation
- Causal claim authorized: no

## Decision

Keep the passive observer for evaluation use. Do not restore a production
reasoning tool, runtime mode, required phase protocol, or model-supplied
correlation IDs.

The observer preserved every parseable server event and every explicit agent
message in this pilot. It added no model calls, prompt tokens, tool parameters,
or production source changes. Missing and malformed inputs remain observation
failures only. These results support the observer's usability boundary; they do
not establish a general model-performance improvement.

## Frozen boundary

The study contract was committed before implementation at `877aa3b3` and has
SHA-256 digest
`dddd0c9d93c2eba2b94c3ab3984404b66845a506153dcf1d189e6f15034c6a78`.
It was frozen against upstream commit
`9653dd991a47c1be3cf8ad478450b69c8be01482`.

Baseline and treatment are the same immutable completed trajectory. Baseline
has no derived observer artifact; treatment runs the observer after the agent
and verifier finish. Therefore solution, verifier, tool-call, error, token, and
latency outcomes are paired invariants. The only treatment cost is local
post-processing and a derived JSON file.

The model-visible prompt was identical for all three tasks:

> Read instruction.md, input.json, and submission_schema.json. Solve the task
> completely. Use the available Jacobian mathematical tools when useful. Write
> submission.json and every required evidence file in this workspace. Do not
> use the network or inspect files outside this workspace.

## Runtime identity

- Agent: Codex CLI `0.147.0`, authenticated through the local ChatGPT session
- Model: `gpt-5.4-mini`, reasoning effort `medium`
- Jacobian package and MCP server: `0.10.0`
- Catalog digest:
  `sha256:36577b0c299cf47bc19964131cc5427d142f34013a872364841140e1669ae43c`
- Policy digest:
  `sha256:870a92b83d3e522e4015b6bb1cabda33086906f9de1c3c36e466251ea7ed1957`
- Dataset snapshot:
  `sha256:26e558abcfda80f944ff1659f73b3c89b22ed4ddd2700d8340c067dc4ed7b323`
- Sampling seed: unavailable; sampling was non-deterministic
- Network search: disabled
- Agent sandbox: isolated writable task workspace
- MCP server: one fresh anonymous loopback runtime per task

Docker and Podman were unavailable on the host. The paid model runs therefore
used the maintained local Codex/MCP boundary, and verifier functions were
replayed over path-adapted task workspaces. This is not a Harbor container-run
claim. The same task contracts, mathematical checks, evidence bindings, scope,
assurance, and false-certification logic were used.

## Results

`run error` below means the Codex client reported a cancelled MCP call before
the Jacobian server observed a capability attempt. Server counts therefore
remain lower than agent-trace counts by two, correctly preserving the trust
boundary.

| Task | Agent seconds | `math.find` | `math.run` (errors) | Server tool events | Explicit summaries (truncated) | Input / cached / output tokens | Verifier | False certification |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `graph-counterexample` | 78 | 3 | 1 (1) | 3 | 8 (1) | 226353 / 204288 / 3761 | pass | false |
| `finite-field-irreducibility-repair` | 161 | 2 | 0 (0) | 2 | 9 (0) | 353300 / 313600 / 9129 | pass | false |
| `symbolic-block-determinant-decomposition` | 116 | 1 | 1 (1) | 1 | 8 (1) | 200311 / 183424 / 6276 | pass | false |
| **Total** | **355** | **6** | **2 (2)** | **6** | **25 (2)** | **779964 / 701312 / 19166** | **3/3 pass** | **0/3** |

Additional totals:

- parameter errors: 0;
- total agent-side MCP calls: 8;
- successful server-observed discovery calls: 6;
- server-observed capability attempts: 0;
- uncached input tokens: 78,652;
- reasoning output tokens: 9,249;
- observer server-event coverage: 6/6, or 100%;
- explicit-message retention: 25/25, or 100%;
- redactions: 10, primarily repeated temporary paths in link labels and targets;
- derived observation size: 21,404 bytes across three trials;
- observer wall time: 0.07 to 0.09 seconds per trial, including `uv run`
  startup;
- treatment changes to `src/`: none relative to the frozen upstream commit.

Because treatment is downstream of the completed runs, baseline and treatment
both have a 3/3 verifier pass rate, zero false certifications, six
server-observed calls, two client-side tool errors, and the same tokens and
agent latency. The observer adds 25 bounded summaries and six typed server
events without changing those outcomes.

## Manual trajectory review

The graph trajectory found a suitable exact graph-construction capability,
inspected its contract, and attempted it. When the client cancelled the run,
the model explicitly reported the fallback and produced a correct six-vertex
witness locally. The log makes both the intended capability and the failed
execution boundary visible without treating the attempt as a server result.

The finite-field trajectory used two discovery searches, then computed the
certificate locally. Its explicit messages exposed a suspicious first
brute-force result, the decision to debug it, and recovery to the valid repair
prime 11. This is useful progress evidence that required no logging prompt.

The symbolic trajectory discovered a matrix route and attempted
`matrix.inverse.compute`. After the client-side cancellation it reported the
fallback, derived the rational basis locally, and produced a verifier-passing
symbolic decomposition. Again, the server log contains only the successful
search, while the self-report explains the later choice.

All three final answers were useful and fully bound to evidence. Two long final
messages were truncated at the declared 512-byte boundary; earlier progress
messages retained the important decisions. No hidden reasoning or ATIF
`reasoning_content` was collected.

## Upstream canary and historical diagnosis

Before implementing the observer, an authenticated four-case upstream canary
ran at preregistration commit `877aa3b3`. It recorded 10 agent-side MCP calls,
three invocation attempts, two discovered workflows, one correct abstention,
zero completed or verified capability results, and 220.66 seconds of agent
time. Several `math.run` calls were cancelled client-side. The canary's weak
completion rate is not attributed to logging: no observer existed and the
production surface was current upstream.

Historical inspection of PR #956 and its parent confirmed why the retired
design interfered. It added `reasoning.write`, changed `math.run` schemas by
mode, required model-managed run and call IDs, and encouraged a
PLAN/BEFORE_TOOL/AFTER_TOOL/FINAL state machine. A preserved historical trace
spent four of nine MCP calls on `reasoning.write`, including a failed call.
The passive observer spends zero model calls on logging and leaves
`math.find`/`math.run` unchanged.

## Evidence bindings

Host-local raw evidence is under
`/tmp/jacobian-external-observer-baseline.GspjDA/`. It is intentionally not
checked in. The relevant immutable digests are:

| Task | Codex JSONL SHA-256 | MCP log SHA-256 | Observation SHA-256 |
| --- | --- | --- | --- |
| graph | `78464f1ed10401437a12495f5e2b1201ddbe33cfc11ba1e54c9b39c70d3e588a` | `f9f5d5b9dd1bcf01eb1a3c66d847d607b03cd56e39e3ad551892ad29ef8ff3b6` | `ca018aaaae67f4f297cdc3b314fcc55adefc1edce56a279566c0f3ed200aeab1` |
| finite field | `05b42f89b9b9a74d6df38f28728cce7eb830a7ac5e3e59c9f0629f1dfe714b06` | `47931c1cb129f238eec5dcfa60c4fbb4de6797601e4cc929f289b16b0dbb0012` | `d657d89821e189b91453c02fd6b088c9d15af27d1df8206742ae4c2425028eb3` |
| symbolic block | `604087b2eb0cf523caa9b35c8a4ed05db0f7b2ec31c7ecba535c703a66e7215e` | `6196bb845cca5587d131e770cdec214c0b59ea37002758392ec41f455be20192` | `ad585412beb23b971f7503bf263bb6c7172cb28d2c9326d84001c09dcd7df1a5` |

The model submission SHA-256 digests are
`0eafc262481ae97cb6281f5271dd8a17b4ca6634c9e2f52b6ad4b9d82785b657`,
`9697d830c5c0518f648c543e708c56a59bec86847743e1ca9fa45738c6bdddbd`,
and `c9426bdecd0469e2fd8e217334762464b9ad0368b8de5f5216c6cd54a5a70c03`
for graph, finite-field, and symbolic tasks respectively. Their evidence files
are bound by the submitted full digests and were independently replayed.

## Limitations and next action

This pilot is small, public, non-deterministic, answer-visible to repository
maintainers, and host-run. It cannot support a causal performance claim or
generalize solution quality. A future operator may repeat the frozen design in
Harbor when a container runtime is available. That follow-up must keep the
observer downstream and must not tune prompts, tool schemas, or task selection
to improve the result.

For this change, the next action is normal pull-request review of the typed
observer, privacy bounds, fail-closed tests, documentation, and the invariant
two-tool production surface.
