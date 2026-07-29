# ADR 0004: Verify parameter regions through immutable subjects

[Documentation home](../../index.md) · [Decision log](index.md)

- Status: Accepted
- Date: 2026-07-24

## Decision

Allow hypothesis plugins to return only `PROPOSED` or `SAMPLED`
parameter-region evidence. Before verification, store an immutable
`ParameterRegionSubject` binding:

- the target claim artifact;
- whether the claimed region is `SUFFICIENT` or `NECESSARY`;
- canonical exact conditions;
- cited sample artifacts.

Promote a region only when an authorized certificate verification record:

- binds the claim and subject object digests;
- includes the exact claim and subject artifact URIs as parents;
- has conclusion `TRUE`;
- replays to the identical verification-record URI.

The runtime assigns the verified label from the subject kind only after
those checks. The authorized domain checker defines what the conditions mean
and whether the certificate proves them.

## Rationale

The plugin that proposes a region is mathematically untrusted and cannot
authorize its own checker or attach a verified label.

The subject gives a checker one immutable candidate to certify. Requiring exact
artifact parents as well as object digests closes a carrier-substitution gap:
two artifacts can contain the same canonical object while recording different
lineage or summary metadata.

Requiring replay to reproduce the same verification-record URI binds promotion
to checker identity, executable digest, request, environment, evidence, and
conclusion without creating a second region-specific trust mechanism.

## Alternatives considered

### Let the plugin emit a verification record

Rejected because it collapses proposal and authorization into the same
untrusted component.

### Bind only the canonical conditions digest

Rejected because the target claim, sufficient/necessary relation, samples, and
artifact lineage would remain substitutable.

### Add parameter mathematics to the generic runtime

Rejected because sufficiency and necessity are domain semantics. The runtime
should enforce evidence and identity boundaries, not reimplement every
certificate checker.

### Add a separate region-verification service

Rejected because the existing certificate registry, replay service, and
verification records already provide the required trust boundary.

## Consequences

- Parameter-region proof formats remain checker-defined.
- Equal payloads in different artifact carriers are not interchangeable for
  promotion.
- Sample citations must be explicit workflow evidence and subject parents.
- Revoked or incompatible checkers cannot create a new promoted result.
- CLI and MCP promotion remain thin adapters over the same service method.
