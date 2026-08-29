# Direct MCP catalog evaluation v1

This evaluation supports retaining `math.run` for now and retaining `math.find`
as optional semantic-vocabulary discovery rather than as a required execution
step. Direct typed tools are functionally promising, but two predeclared
`math.run` removal gates remain unmeasured: observable deferred client discovery
and exact per-task loaded tool-definition bytes.

The corpus and decision policy were frozen before the accepted runs. Results
below were collected on 2026-08-29 from repository revision
`db3d5f418e9d9a9af957d04b941a388e18e680bc`, Codex CLI 0.150.1,
`gpt-5.6-sol` at high reasoning effort, Python 3.12.13, MCP SDK 2.1.0, and
macOS arm64.

## Frozen question and corpus

The local suite digest is
`sha256:94473c773a84200338e18d872c9ee8a28ae9c2ee2416ffe6eb2a409e78b054dd`.
The real-client suite digest is
`sha256:8a8a0faa7eb11f501bf52f7f880a68bcda0f85d2a3dc601e62fde5cef11df8cc`.

| Family | Frozen execution case | Required operation |
| --- | --- | --- |
| Straightforward | Exact determinant | `matrix.determinant.compute` |
| Alternate terminology | Sandpile group | `graph.chip_firing.critical_group.compute` |
| Postcondition distinction | Complete indexed subset-sum multiplicities | `additive.subset_sum.profile.compute` |
| Structural ambiguity | Sparse typed polynomial GCD over `QQ[x]` | `polynomial.compute.gcd` |
| Multi-operation | Canonical CNF passed unchanged to assignment check | `sat.cnf.canonicalize`, `sat.assignment.check` |

Two additional cases asked only for semantic discovery: the sandpile synonym,
and the nearby critical-group/q-reduced-divisor vocabulary.

Before execution, removal of `math.run` was conditioned on complete schema
coverage, exact local direct/legacy parity and composition, two real-client
repetitions per case with 100% direct success and no higher per-case failure
rate, observed deferred client discovery, and exact loaded-definition bytes no
larger than the legacy arm. Evidence of unique `math.find` value required a
repeated improvement over direct-only execution in at least two independent
mathematical families.

## Catalog-scale controls

| Measurement | Result |
| --- | ---: |
| Catalog operations / advertised direct tools | 769 / 769 |
| Total advertised MCP tools | 771 |
| Complete direct input/output schema coverage | Yes |
| All tool-definition bytes | 2,647,576 |
| Direct tool-definition bytes | 2,635,991 |
| `math.find` + `math.run` definition bytes | 11,586 |
| Direct input/output schema bytes | 2,317,802 |
| Server construction | 946.885 ms |
| `tools/list` median / p95, 7 repetitions | 43.492 / 93.581 ms |
| Frozen discovery probes | 6/6 |
| Direct tasks / legacy tasks / exact parity | 5/5 / 5/5 / 5/5 |
| Exact typed multi-operation composition | 1/1 |
| Local semantic-discovery cases | 2/2 |

The direct definitions required by the five known selected operations were
2,579, 1,641, 4,153, 5,253, and 3,257 bytes respectively. These are useful
lower-bound estimates, not measurements of what the client loaded into model
context.

The semantic searches ranked the sandpile operation first. The neighborhood
query ranked `graph.chip_firing.q_reduced.compute` first and
`graph.chip_firing.critical_group.compute` second, in 2.488 ms locally.

## Real-client observations

Each execution case ran twice in a fresh isolated Codex home. Both primary
arms used the same suite, model, catalog/tool-definition snapshot, runner hash
`sha256:dfa9a10117631cb7ffdbe3649aaaeb8996752d18be08d2c009d0949da11acf00`,
and telemetry-parser hash
`sha256:f9f31775f1e606d65da26e8a22e931b28e579f743651c9e3a9850288d0b14235`.
Only the predeclared client-visible surface filter differed between arms.

| Case | Direct success | Legacy success | Direct calls | Legacy calls |
| --- | ---: | ---: | ---: | ---: |
| Exact determinant | 2/2 | 2/2 | 2 | 6 |
| Sandpile group | 2/2 | 2/2 | 2 | 6 |
| Complete subset-sum profile | 2/2 | 2/2 | 3 | 6 |
| Polynomial GCD | 2/2 | 2/2 | 2 | 6 |
| CNF composition | 2/2 | 2/2 | 4 | 12 |
| **Total** | **10/10** | **10/10** | **13** | **36** |

Neither arm had a command failure, tool error, parameter error, or failed
operation attempt. Direct execution also completed the CNF composition in both
unified-exec repetitions, using exactly two direct calls each time.

| Arm | Visible tools | Eager definition bytes | Success | MCP calls | Uncached input tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| Legacy execution | 2 | 11,586 | 10/10 | 36 | 214,447 |
| Direct execution | 769 | 2,635,991 | 10/10 | 13 | 208,960 |
| Direct + `math.find` subset | 770 | 2,645,523 | 4/4 | 4 | 91,917 |
| `math.find` semantic-only | 1 | 9,533 | 4/4 | 12 | 79,225 |
| Direct unified composition | 769 | 2,635,991 | 2/2 | 4 | 41,601 |

The direct arm used fewer MCP calls and 5,487 fewer uncached input tokens than
the legacy arm in this repetition. The token difference is small relative to
the stochastic totals, and neither observation identifies which tool
definitions the client loaded.

The direct-plus-find subset covered the synonym and postcondition families.
None of its four runs used `math.find`; all four completed, but direct-only had
already completed both families in both repetitions. Thus this small corpus
observed zero families with an end-to-end improvement attributable to
`math.find`. The semantic-only arm nevertheless found all required vocabulary
in all four repetitions. Its fail-closed discovery contract also confirmed zero
`math.run` calls, zero direct-operation calls, and no attempted or completed
operation in every run.

Codex JSONL exposed the configured surface sizes and token accounting, but not
which definitions client-managed tool search actually loaded. Consequently,
`exact_loaded_tool_definition_bytes` is `null` in every report. The token
totals above cannot substitute for that missing measurement. Wall time is also
descriptive only because arms ran concurrently and model sampling is
stochastic.

## Decision against the frozen gates

| `math.run` removal gate | Outcome | Evidence |
| --- | --- | --- |
| Complete catalog schema coverage | Pass | 769/769 direct schemas |
| Exact local typed parity | Pass | 5/5 tasks |
| Direct multi-operation composition | Pass | Local 1/1; Codex direct 2/2; unified 2/2 |
| Repeated real-client noninferiority | Pass | Every case 2/2 in both arms; zero failed attempts |
| Observed deferred client discovery | **Unmeasured** | Current JSONL does not identify the client search/load event |
| Exact per-task loaded-definition bytes no larger than legacy | **Unmeasured** | Current JSONL exposes no exact loaded-definition byte count |

Recommendation for issue #2982:

- Retain `math.run`. Direct tools should remain available and continue to be
  evaluated, but this evidence does not satisfy the predeclared removal policy.
- Retain and re-scope `math.find` as optional mathematical-vocabulary discovery,
  independent of execution. It is locally and externally usable, but unique
  improvement over client-managed direct-tool discovery was not established.
- Revisit removal only with a client trace that exposes deferred search and
  exact loaded definitions, then repeat this frozen corpus with more models and
  a larger held-out mathematical sample.

## Evidence identity and reproduction

| Report | SHA-256 |
| --- | --- |
| Deterministic catalog controls | `1f531be93c158567891e8887dfdf709d073f2aa9c3260573fd63e25ea861501b` |
| Direct, two repetitions | `0b51940751c3db1f1b13137a9e995edc5865211067f8405a9782d413d114d13c` |
| Legacy, two repetitions | `7d831873180839607028a7ed1c89a37306ff0552ddf10a5401dd2d984e7e2653` |
| Semantic `math.find`, two repetitions | `94c8f7bc5223d30de31ab6b2213f099d8c8f410c55aa3e729332b2ae9dadd8ae` |
| Direct + `math.find`, two repetitions | `34d43a6036e934fdd0178603cf5d673f5b4d67d619b60e7ae52053c3c44da6c3` |
| Direct unified composition, two repetitions | `5b4167d9d82acde2b123df62e049271e50a733a8dfe40fc90098ce164f008709` |

The raw reports and transcripts are intentionally uncommitted operator output.
Use the commands and evidence-bound report fields documented in
[the MCP visibility evaluation guide](../../docs/run-codex-visibility-evaluation.md)
to reproduce them. This is an adoption diagnostic, not broad mathematical
correctness evidence or a causal latency study.
