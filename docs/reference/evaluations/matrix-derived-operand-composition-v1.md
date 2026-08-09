# Matrix derived-operand composition study

## Decision

`stage=evaluation,status=complete,disposition=inconclusive-prototype-reverted`

Do not ship the evaluated `matrix.multiply.compute` request-local
`derived_operand` prototype. The frozen treatment preserved terminal acceptance
and produced two valid derived-operand calls without false certification, but
only one of three task lineages used it. Both uses computed `D D^T` where the
task needed `D^T D`, and mathematical correctness on that lineage fell from
2/2 baseline trials to 1/2 treatment trials. The preregistered keep gate
required demonstrated use across two lineages.

The evidence does not justify a generic transform capability, an artifact
handoff for ordinary values, JSON pointers, a request expression language, or
a standalone matrix transpose capability. Issue #28 should remain closed as
not solved. A later proposal needs evidence for a more legible operand-order
contract and a held-out task that actually exercises it correctly.

## Frozen identities

- Upstream source: `0052a5bf78f63f5539be13da6493abb395c5026d`
- Preregistration and baseline product revision:
  `aacf3104edb222124d04b538412c5cc0ad3a8ce0`
- Treatment implementation revision:
  `15b3364695c1ab4458778286a47fdcbf4eb338a2`
- Reverted final-tree revision before this handoff:
  `3d212b56110295bcdccb9cec8b8fa3d072915bb0`
- Installed capability count: `334`
- Operator policy digest:
  `sha256:870a92b83d3e522e4015b6bb1cabda33086906f9de1c3c36e466251ea7ed1957`
- Study config digest:
  `sha256:ab63e1f5214caf94807c7e2d891272ddb2d25dc7a11967fc91d258dcc59b6c66`
- Wrapper digest:
  `sha256:ac233e5140368070c799d5d4261f6281d189a28038c7aa643adb401fba13008d`
- Base host-runner digest:
  `sha256:d4338bfb77e3e5fccfaa149df186a8afc1191b3ef00e8ed916ea8928fd8cb320`
- Baseline model-cache digest:
  `sha256:fa53edf6c1e5c48ee663b928981f82ac78ab110b8fd7d1918ec57b405b379fa6`
- Treatment model-cache digest:
  `sha256:d9bd073a79fe9e89c44691400771a0b513010ee54d5ceef35abb95fabf6294c5`
- Codex: `codex-cli 0.147.0`, `gpt-5.4-mini`, reasoning `medium`
- Runtime audit: `uv 0.12.1`; Lean 4.31.0 and the optional external SAT
  proof executables were absent as expected and unrelated to the matrix bundle.
- Container limitation: neither Docker nor Podman was installed. This is a
  digest-bound host-local semantic-tool observation, not a Harbor run or a
  causal estimate.

The baseline ran in tmux session `jac-issue28-baseline` from
2026-08-09T15:32:22Z. The treatment ran in `jac-issue28-treatment` from
2026-08-09T15:57:09Z to 2026-08-09T16:14:35Z. Each rollout copied only the
three public task files into an isolated workspace. The unchanged task-owned
verifier then ran in a fresh child process. No API key was forwarded, web
search was disabled, and every started rollout was retained without retry.
The raw model-cache file changed between batches, so its digests differ. The
selected `gpt-5.4-mini` catalog records stored in the manifests are byte-for-byte
equal after canonical JSON ordering, as are the CLI version, reasoning effort,
task contracts, study config, wrapper, and base runner. This cache drift is an
additional reason the host-local results are descriptive rather than causal.

## Discovery handoff

### Recurring move

The open-workflow evidence contains four independent mathematical contexts
where an already-present matrix must be reused directly or under transpose:

1. The differential-poset issue trajectory needed `A A^T`. It found matrix
   multiply and verify, but made four invalid compute calls: three omitted the
   required `right` operand and one misplaced `left` outside the input payload.
   All failed closed with `INVALID_REQUEST`; the agent manually computed the
   Gram matrix and withheld `VERIFIED`.
2. `matrix-square-zero-counterexample` needs `A A`.
3. `lagrangian-projection-proof-audit` needs `D^T D` and `D^T J D`.
4. `hadamard-order12-construction` needs `H H^T`.

Current main already supports the two ordinary composition cases that must not
be displaced:

- Small typed producer results remain inline and feed downstream request
  models directly. For example, RREF's `reduced_matrix` is already a
  `RationalMatrix` accepted by matrix multiplication.
- Durable artifact references compose retained evidence. Graph Atlas results
  feeding graph-property operations are the canonical example.

The missing move is narrower: construct one matrix product operand from its
sibling inside the same request without copying a potentially large value.

### Catalog overlap and alternatives

- `matrix.multiply.compute` already owns the exact product outcome and was the
  only capability extended in the prototype. A new Gram or transpose
  capability would duplicate an outcome or add a primitive without enough
  independent workflow evidence.
- `transform.apply` is a plugin-selected transformation of durable artifacts
  with schema and semantics bindings. Reusing it for ordinary inline values
  would reverse the current typed-value architecture and make a simple product
  depend on untrusted plugin transformation.
- Re-materializing every ordinary matrix solely for handoff was rejected by
  the earlier topology migration: main deliberately retained artifacts for
  evidence while returning ordinary mathematical values inline.
- A generic JSON pointer, value handle, recursive expression, or cross-request
  reference would create a new composition language and move semantic
  ownership into the generic kernel. The evidence supports no such expansion.
- Better generic recovery diagnostics were evaluated separately and did not
  establish a portfolio-wide product change.

## Evaluated treatment

The prototype added one optional, versioned field to
`matrix.multiply.compute`:

```json
{
  "left": {"entries": "<bounded RationalMatrix entries>"},
  "derived_operand": {
    "operand_derivation_version": "1",
    "source": "LEFT",
    "target": "RIGHT",
    "transform": "TRANSPOSE"
  }
}
```

The only transforms were `IDENTITY` and `TRANSPOSE`. Source and target had to
differ; the source had to be explicit; the target had to be omitted; and the
request resolved exactly one sibling operand before SymPy multiplication.
Cycles, two references, arbitrary expressions, JSON pointers, artifacts, and
cross-request state were impossible. Existing explicit two-operand requests
remained valid. The capability version was raised to `2` in the prototype.

The computed result remained capped at `COMPUTED`. The request, including the
derivation and omitted target, remained visible in the result scope.

### Independent-checker obligations

| Obligation | Bound input | Rejection condition | Independent method |
| --- | --- | --- | --- |
| Request shape | exact input payload and derivation version | unknown field, version, or transform | strict dictionary and enum checks |
| Sibling binding | source, target, explicit source, omitted target | equal endpoints, missing source, or populated target | independently parse the checker claim |
| Transform relation | exact rational source and target role | derived matrix differs from identity/transpose relation | Python-FLINT identity or transpose replay |
| Product relation | resolved left and right matrices | candidate differs from exact product | Python-FLINT multiplication |
| Shape metadata | rows, inner dimension, columns | any declared dimension differs | compare against resolved FLINT matrices |
| Claim and candidate identity | canonical payload digests | digest, operation, or witness-format mismatch | existing operator-authorized checker envelope |

Focused tests at the treatment revision covered valid left/right sibling
derivations, incompatible and cyclic requests, populated targets, missing
sources, an independently verified square, a changed transform, a false
product, and direct checker attacks. The focused lane passed `27` tests. This
test evidence proves the bounded contract and fail-closed checker behavior; it
does not establish agent value.

## Evaluation design

The preregistration is
[`benchmarks/config/matrix-derived-operand-composition-v1.json`](../../../benchmarks/config/matrix-derived-operand-composition-v1.json).
It froze three public tasks, two repetitions per condition, 600 seconds per
rollout, and the unchanged task-owned verifier as the only terminal reward.

| Task | Harbor task digest | Verifier bundle digest | Intended move |
| --- | --- | --- | --- |
| matrix-square-zero-counterexample | `65887808...9c8a` | `72e83028...a9dd` | `A A` |
| lagrangian-projection-proof-audit | `34e1438c...ca3` | `24048bd8...9c5f` | `D^T D`, `D^T J D` |
| hadamard-order12-construction | `2b98acc7...b3ea` | `576a555e...c4fb` | `H H^T` |

The keep gate required treatment to preserve or improve terminal acceptance
and demonstrate at least two valid derived calls across at least two task
lineages without false certification. Use in only one lineage was explicitly
insufficient.

## Results

| Metric | Baseline | Treatment |
| --- | ---: | ---: |
| Terminal accepted | 2/6 | 2/6 |
| Terminal rejected | 4/6 | 4/6 |
| False certification | 0 | 0 |
| Capability input rejections | 0 | 0 |
| Matrix multiply calls | 2 | 5 |
| Derived-operand calls | 0 | 2 |
| Task lineages using derivation | 0 | 1 |
| Input tokens | 2,438,722 | 2,173,347 |
| Output tokens | 54,873 | 48,943 |

All twelve trajectories completed the reasoning-log protocol. The identical
2/6 terminal result is not a treatment win: the four rejections in each
condition were task evidence/protocol failures, and the treatment did not fix
them.

The two treatment derivations occurred in the two projection-audit trials.
Both were valid `matrix.multiply.compute` calls with zero request rejections,
but both formed `D D^T`. The task required `D^T D`. One treatment projection
trial subsequently recovered enough mathematics manually; the other failed
the mathematical verifier. Projection correctness therefore moved from 2/2 in
baseline to 1/2 in treatment. Neither square-zero treatment used `IDENTITY`,
and neither Hadamard treatment used `TRANSPOSE`; those agents continued to
duplicate the small square matrix or compute the Gram matrix manually.

The lower treatment token totals are reported descriptively only. With two
unpaired samples per task, nondeterministic model trajectories, no container
runtime, and no terminal improvement, they do not support a causal efficiency
claim.

Raw baseline evidence is in
[`benchmarks/results/matrix-derived-operand-composition-v1-baseline`](../../../benchmarks/results/matrix-derived-operand-composition-v1-baseline/manifest.json).
Raw treatment evidence is in
[`benchmarks/results/matrix-derived-operand-composition-v1-treatment`](../../../benchmarks/results/matrix-derived-operand-composition-v1-treatment/manifest.json).
Each manifest binds the product revision, task/public/verifier digests, model
record, tmux session, runner digests, and every retained artifact.
The exact raw files, including transcripts, reasoning logs, MCP logs, copied
public workspaces, and clean-room verifier outputs, are preserved in the
adjacent
[`baseline archive`](../../../benchmarks/results/matrix-derived-operand-composition-v1-baseline.tar.gz)
and
[`treatment archive`](../../../benchmarks/results/matrix-derived-operand-composition-v1-treatment.tar.gz).

## Next action

Keep issue #28 closed and attach this study as negative/inconclusive evidence.
Do not close it as solved. If a future candidate is pursued, start a new
discovery handoff that addresses operand order directly, for example by
evaluating a target-local typed reference rather than reusing this prototype's
separate `derived_operand` record. Freeze a held-out task where successful use
of `A^T A` and `A A^T` is distinguishable, and require correct semantic use in
two lineages before implementation is retained.

No checker or mathematical obligation remains in the final tree because the
prototype was reverted. The open obligation is product discovery: identify a
bounded request shape that agents both discover and apply with the intended
operand order.
