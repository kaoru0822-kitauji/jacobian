# SMT Alethe artifact contracts

[Documentation home](../index.md)

- Status: Experimental pre-stable producer contract
- Optional operation: `smt.unsat_proof.find` when the exact cvc5 1.3.4
  Python distribution is installed
- Verification operation: not yet installed; a compatible independent
  Carcara adapter is the next portfolio checkpoint
- Related plan:
  [Atomic capability portfolio](../contributing/atomic-capability-portfolio.md#wave-3-theory-bounded-smt-proof-slice)

Jacobian's first SMT slice preserves one exact quantifier-free SMT-LIB query
and the raw Alethe bytes emitted by cvc5. It does not expose a broad
`smt.solve` workflow. A cvc5 `unsat` report, stored proof bytes, or the absence
of lexical `hole` markers is computed evidence, not independent verification.
Every producer result therefore carries `conclusion: UNKNOWN`.

Install the optional wheel-backed provider with:

```sh
uv sync --extra smt
```

The locked development environment also includes the exact provider so the
producer contract and public reproduction cases run in CI.

## Registered descriptors

`JacobianKernel.smt.installation` exposes the content-addressed descriptor URIs
registered by the current kernel:

| Descriptor | Registered name and version | Purpose |
| --- | --- | --- |
| Semantics | `jacobian.smt.qf-unsat@1` | Quantifier-free single-query meaning and evidence boundary |
| Schema | `jacobian.smt-problem@1` | Exact bounded SMT-LIB 2.6 input |
| Schema | `jacobian.smt-alethe-proof@1` | Raw cvc5 Alethe bytes bound to one exact input |

The schemas are model backed. Their closed structural and cross-field
invariants also apply when a payload is submitted through `artifact.put`.
Kernel construction registers the artifact boundary even when cvc5 is absent;
only the producer capability is conditional.

## Pinned SMT-LIB profile

Profile `jacobian.smtlib2.qf-unsat/v1` admits exactly one query in one of:

- `QF_UF`;
- `QF_LIA`; or
- `QF_LRA`.

The source is at most 1,000,000 ASCII bytes, uses LF line endings, ends in LF,
and has a maximum parenthesis nesting depth of 512. Its top-level commands are
limited to:

- one leading `set-logic` equal to the separately declared logic;
- `declare-sort`, `declare-fun`, or `declare-const`;
- zero or more `assert` commands; and
- one final argument-free `check-sat`.

Incremental commands, solver-option changes, definitions, assumptions,
result-retrieval commands, reset, include, multiple queries, quantifiers, and
theories outside the selected logic are not part of version 1. The contract
scanner handles comments, strings, and quoted symbols when identifying
top-level command boundaries. The isolated cvc5 parser then independently
rejects source that is not valid in the declared logic.

The problem artifact preserves the exact text and SHA-256 digest. It does not
claim that equivalent presentations have one canonical identity.

## Provider identity and isolation

The catalog entry requires the exact `cvc5==1.3.4` distribution with the
expected parser, solver, proof-component, and proof-format APIs. Its runtime
record uses:

- install tier `T1`;
- license identifier `BSD-3-Clause`;
- digest kind `PYTHON_DISTRIBUTION_RECORD`;
- feature flags `smt-lib-2.6` and `alethe-proof-production`; and
- profile and proof-format configuration.

The digest identifies the installed wheel RECORD manifest; it does not claim
to rehash every package byte. Provider identity and successful execution
remain separate from mathematical assurance.

The adapter does not call the native solver in the MCP server process. It
starts an isolated Python worker in its own bounded process group, fixes locale
and timezone, and applies the declared wall-time both as cvc5's
`tlimit-per` and as a parent process deadline. Worker stdout is a closed JSON
protocol capped at 4 KiB, stderr is capped at 64 KiB, and raw proof capture is
capped at 6,000,000 bytes. Timeout or stream overflow terminates descendants.

## Alethe proof production

`smt.unsat_proof.find` accepts:

```json
{
  "logic": "QF_UF",
  "smtlib_text": "(set-logic QF_UF)\n(assert false)\n(check-sat)\n",
  "resource_budget": {
    "wall_seconds": 5
  }
}
```

The adapter first materializes the exact input problem, then invokes cvc5 with
proof production enabled and serializes the full proof as Alethe. An
`UNSATISFIABLE` solver report is usable only when the worker also creates one
bounded regular proof file and its reported lexical hole count matches the
captured bytes.

The proof artifact binds:

- the problem artifact URI, object digest, payload digest, logic, profile,
  language, and exact SMT-LIB digest;
- format `ALETHE` and version `cvc5.alethe/1.3.4`;
- exact proof bytes as canonical base64 plus their SHA-256 digest;
- the exact cvc5 provider runtime;
- the enforced wall-time budget; and
- `alethe_hole_count` plus `contains_holes`.

Hole metadata is an inspectable routing signal, not proof checking. It counts
the exact byte marker `:rule hole`; it does not establish that every other rule
is supported or valid.

The result reports `PROOF_PRODUCED`, the problem and proof URIs, solver status,
and hole metadata at assurance level `COMPUTED`. `SATISFIABLE` or `UNKNOWN`
returns `NO_PROOF_PRODUCED`; it does not produce a model, prove SAT, or imply
anything from failure to find a proof.

## Reproduction cases

The pinned public spike exercises three small cases:

| Logic | Query shape | Observed producer behavior |
| --- | --- | --- |
| `QF_UF` | `a = b` and `not (a = b)` | Alethe produced with zero lexical holes |
| `QF_LIA` | integer `x >= 1` and `x <= 0` | Alethe produced with at least one explicit hole |
| `QF_LRA` | real `x > 1` and `x < 0` | Alethe produced with explicit holes |

These observations are version-bound regression cases, not a compatibility
claim for all inputs in a logic. cvc5's own
[Alethe output documentation](https://cvc5.github.io/docs/latest/proofs/output_alethe.html)
also shows that proof output may contain untranslated rewrites represented as
holes.

## Fail-closed boundary

No proof artifact is retained when:

- source validation or the cvc5 parser rejects the query;
- the worker times out, crashes, or exceeds an output limit;
- its JSON protocol, status, proof-presence flag, or hole count is malformed;
- a non-UNSAT status carries proof material;
- an UNSAT status lacks one bounded regular proof file; or
- the proof bytes disagree with the worker's hole metadata.

Operational failure returns `ERROR` or `TIMEOUT`, heuristic assurance, and no
mathematical conclusion. The already materialized exact problem may remain as
the operation's sole artifact.

The next slice will pin a separately installed compatible
[Carcara](https://github.com/ufmg-smite/carcara) revision, define its supported
rule and theory intersection, replay adversarial mutations, and expose
`smt.unsat_proof.verify` only through operator-authorized checker identity.
Until then there is no SMT path to `VERIFIED`.
