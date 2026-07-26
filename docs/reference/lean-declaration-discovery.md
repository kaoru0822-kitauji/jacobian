# Lean declaration discovery

Jacobian exposes two read-only `EXPLORE` capabilities over the installed,
pinned Lean runtime:

- `lean.declaration.search` performs bounded declaration retrieval; and
- `lean.declaration.inspect` resolves one exact declaration name.

They return computed environment metadata. Finding or inspecting a theorem does
not verify a new claim. Completed proof source must still pass `lean.check`.

## Search contract

`lean.declaration.search` accepts:

- `environment`: `CORE` or `MATHLIB`;
- `name_contains`: an optional case-sensitive declaration-name substring;
- `type_pattern.constants`: an optional list of one to eight exact Lean
  constant names, all of which must occur in the elaborated declaration type;
- optional `namespace_prefixes` and declaration `kinds`; and
- `result_limit`, from 1 through 50.

At least one of `name_contains` or `type_pattern` is required. If both are
present, both must match. Type patterns inspect constants in Lean's elaborated
expression. They are not pretty-printed text matching, unification, typeclass
search, or proof search.

The provider excludes private declarations and visits public declaration names
in deterministic `Name.lt` order. Each result carries its elaborated
pretty-printed type, declaration kind, namespace when present, optional source
module and range, and explicit match reasons.

`stop_reason` separates the two possible coverage outcomes:

- `RESULT_LIMIT` means the result budget stopped the scan and completeness is
  `PARTIAL`; and
- `EXHAUSTED` means the deterministic scan exhausted the declared environment
  and filters, so completeness is `COMPLETE` with `COMPUTED` assurance.

An exhausted empty result is evidence that this exact scan found no match. It
is not a mathematical nonexistence conclusion.

## Inspect contract

`lean.declaration.inspect` accepts an environment and one exact
`declaration_name`. It returns the declaration's elaborated type, kind,
namespace, documentation and source metadata when available. A missing exact
name is an execution error, not an empty successful result.

## Environment identity and execution bounds

Both outputs carry `environment_digest`. The
`jacobian.lean.environment-manifest/v1` digest binds the selected import,
platform, pinned Lean version, and executable provider digest. `MATHLIB` also
binds the byte digests of `lake-manifest.json` and `lean-toolchain` plus the
authorized Mathlib commit. This is an exact runtime-manifest identity, not an
independent proof certificate.

The `CORE` profile exposes only imported `Init.*` declarations compatible with
the checker profile, even though the provider process also loads Lean
metaprogramming modules to implement the query. Provider-local helper
declarations are never searchable. `MATHLIB` exposes declarations imported by
the pinned `Mathlib` module.

The subprocess is fail-closed, uses `--trust=0`, one worker, a 40-second `CORE`
or 75-second `MATHLIB` timeout, and a two-MiB structured-output limit.
Timeouts, unavailable profiles, malformed output, and Lean errors remain
execution failures without a mathematical conclusion.

See [Retrieve a Lean theorem and check a proof](../tutorials/lean-declaration-discovery.md)
for the public composition.
