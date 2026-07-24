# Milestone 5 specification: federated research corpus

[Documentation home](../../index.md)

- Status: Provisional
- Theme: Extend local memory without confusing retrieval with proof

## 1. Entry gate

The local capability-episode database must have produced a sufficiently
diverse corpus of verified successes, verified failures, computed results, and
unverified runs to evaluate cross-project retrieval quality.

## 2. Integration boundary

Jacobian owns immutable artifacts, verification records, checker authority,
the local research-memory index, and the experiment ledger required for
replay. A federated corpus provider is optional and may run in another process,
package, or service.

The provider may ingest versioned research episodes and return ranked records.
It cannot:

- authorize or install a checker;
- change an artifact or verification record;
- promote a retrieved hypothesis;
- make a conclusion from ranking, clustering, or absence of results.

Provider results carry their corpus identity, query, cutoff, source,
availability, review, retraction, and verification labels. Jacobian validates
referenced local artifacts independently.

## 3. New tools

### `knowledge.search`

The local implementation retrieves trust-labeled capability episodes. M5
extends it with independently selectable provider indexes:

- natural-language text;
- normalized formula structure and quantifier skeleton;
- exact metadata and canonical object hash;
- substructure, motif, witness, or failure type;
- proof or certificate type;
- ancestry;
- temporal cutoff.

### `episode.compare`

Compare retrieved experiments and their verified witnesses, then return
recurring features or a proposed obstruction as an unverified hypothesis.

### `abstraction.extract`

Suggest an interpretable abstraction for supplied artifacts. The result is a
hypothesis artifact with supporting examples and provider provenance.

### `certificate.simplify`

Minimize a certificate according to format-specific objectives while replaying
the authorized checker after every accepted change. This tool uses the corpus
only for discovery; checker replay remains local and authoritative.

## 4. Record lifecycle

The local experiment ledger exists independently of M5. Corpus integration
adds ingestion, canonical deduplication, retention, review, retraction, and
curated promotion without mutating the source records.

Records preserve source publication, first-known, ingestion, verification, and
review dates. Historical queries may impose a knowledge cutoff so retrieval
cannot use a later solution.

## 5. Exit gate

Milestone 5 is complete when:

- all M4 workflows operate correctly without a provider;
- trust and retraction labels survive every retrieval path;
- temporal cutoffs are enforced;
- retrieval improves a held-out search or repair task;
- abstraction tools never promote hypotheses to verified records;
- duplicate and poisoned runs do not dominate results;
- provider compromise cannot alter checker authority or verified records.
