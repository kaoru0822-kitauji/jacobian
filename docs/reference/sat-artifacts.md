# SAT artifact contracts

[Documentation home](../index.md)

- Status: Experimental pre-stable contract
- Installed operations: `sat.model.verify` when the operator installs the
  bundled reference checkers
- Related plan:
  [Atomic capability portfolio](../contributing/atomic-capability-portfolio.md#wave-2-sat-certificate-vertical-slice)

Jacobian installs canonical CNF, total assignment, and raw DRAT proof artifact
contracts without installing a SAT solver. These artifacts begin as typed,
unverified evidence. Storing an assignment does not establish SAT, and storing
proof bytes does not establish UNSAT. An operator may separately authorize the
bundled assignment checker and expose `sat.model.verify`.

## Registered descriptors

`JacobianKernel.sat.installation` exposes the content-addressed descriptor URIs
registered by the current kernel:

| Descriptor | Registered name and version | Purpose |
| --- | --- | --- |
| Semantics | `jacobian.sat@1` | Shared propositional-CNF meaning and evidence boundary |
| Schema | `jacobian.canonical-cnf@1` | Canonical named-variable CNF and DIMACS binding |
| Schema | `jacobian.sat-assignment@1` | Total assignment candidate bound to one CNF |
| Schema | `jacobian.sat-proof@1` | Preserved raw DRAT bytes bound to one CNF |
| Schema | `jacobian.witness-envelope@1` | Exact assignment replay evidence |

The schema URIs are content addressed. They are not capability IDs. The
assignment verification capability appears in `capability://catalog` only
when its checker is operator authorized.

The SAT schemas are model backed. JSON Schema checks their closed structural
shape, and the same registry validation path also applies the domain
cross-field invariants before `artifact.put` commits a payload. Kernel
construction re-registers those model contracts after restart.

## Canonical CNF

`canonicalize_cnf` accepts variable names plus signed integer clauses. Literal
IDs refer to the caller's variable-name order. It then:

1. validates the bounded ASCII variable names;
2. sorts names and assigns contiguous DIMACS IDs starting at one;
3. renumbers every literal through that map;
4. removes duplicate literals and clauses;
5. omits tautological clauses;
6. sorts literals by variable ID and polarity and sorts the resulting clauses;
   and
7. computes the variable-map and deterministic-DIMACS digests.

An empty clause is retained because it is mathematically material. An empty
formula and unused declared variables are also representable. A literal that
is zero or refers outside the declared variable map is rejected.

The deterministic projection is:

```text
p cnf <variable-count> <clause-count>
<signed literals> 0
```

It uses ASCII, one LF-terminated row per clause, and projection version
`jacobian.dimacs.cnf/v1`. The payload records:

- `variable_map_digest`, over the exact ordered symbolic-name map; and
- `dimacs_digest`, over the exact projected bytes.

Consequently, reordering equivalent source input before canonicalization gives
one artifact identity. Presenting a stored payload with reordered canonical
clauses is invalid rather than a second representation.

## Exact CNF binding

Every assignment and proof contains a `SatCnfBinding` with:

| Field | Bound material |
| --- | --- |
| `cnf_artifact_uri` | Exact stored manifest and lineage identity |
| `cnf_object_digest` | Schema-, semantics-, canonicalizer-, and payload-bound object |
| `cnf_payload_digest` | Canonical CNF payload bytes |
| `variable_map_digest` | Ordered symbolic-name to DIMACS-ID map |
| `dimacs_digest` | Exact solver-facing projection |
| `projection_format`, `projection_version` | DIMACS interpretation |
| `variable_count`, `clause_count` | Declared full-instance scope |

`SatArtifactService` derives this record from a stored canonical CNF. It does
not accept a caller-supplied replacement binding, and it records the CNF
artifact as the evidence artifact's parent.

## Assignment artifacts

An assignment is a strict Boolean vector in variable-map order. Its length must
equal `variable_count`; partial assignments are not part of version 1. It also
records:

- declared scope `FULL_CNF`;
- an available `CapabilityProviderRuntime`, including provider version and
  exact runtime digest; and
- the search resource budget, with a required wall-clock bound and optional
  memory and conflict bounds.

The assignment schema has no conclusion, verification status, checker ID, or
certificate claim.

## Assignment verification

`sat.model.verify` accepts one `assignment_uri` in `VERIFY` mode. Before
starting a checker process, its adapter:

1. validates the stored assignment with the model-backed schema;
2. resolves the CNF named inside the assignment;
3. derives the current CNF binding from that stored artifact;
4. requires every binding field to match and the CNF to be an assignment
   parent; and
5. materializes a `sat.assignment@1` witness bound to the exact CNF,
   assignment, and SAT semantics.

The authorized checker then runs in a clean process. Its implementation uses
only the Python standard library and no solver code or Jacobian SAT contract
implementation. It independently validates the closed canonical CNF shape,
variable ordering, clause ordering, payload, variable-map and DIMACS digests,
assignment binding, total strict-Boolean vector, evidence bindings, and
lineage. It returns `TRUE` only after evaluating every clause successfully.

Acceptance creates the ordinary kernel `VerificationRecord` and allows the
capability result to report `VERIFIED`. Assignment rejection reports
`UNKNOWN`: it does not establish UNSAT. A malformed or misbound artifact fails
before checker dispatch. Timeout, checker error, cancellation, and incomplete
execution likewise remain non-verified and carry no SAT or UNSAT conclusion.
Direct witness replay makes no enumeration-completeness claim.

## Raw proof artifacts

A proof artifact preserves the exact raw bytes as canonical base64 and records
their SHA-256 digest. Version 1 binds:

- format `DRAT`;
- format version `drat-text/v1`;
- encoding `BASE64`;
- declared scope `FULL_CNF`;
- the complete CNF binding;
- the exact producer runtime; and
- the producing search budget.

The artifact layer does not parse the proof or infer UNSAT. Malformed,
truncated, or adversarial bytes may be retained as unverified evidence for
later fail-closed replay. The current artifact store has a 10 MiB payload
limit, and this contract bounds the base64 field to 8,000,000 characters.

## Trust boundary

The following are deliberately outside this slice:

- no CaDiCaL invocation or solver-status interpretation;
- no DRAT-trim process or checker authorization;
- no UNSAT conclusion from assignment rejection; and
- no verification of raw proof bytes.

The next slice adds CaDiCaL model and proof production as unverified
exploration. Independent clean-process proof replay remains a later, separate
change.
