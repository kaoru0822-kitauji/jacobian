# Performance benchmarks

## Purpose

Performance benchmarks answer operational questions: how quickly and at what
resource cost can Jacobian store, dispatch, replay, and search? They do not
establish mathematical correctness. Every benchmark target must already pass
its contract and conformance tests.

The initial goal is a reproducible baseline, not an invented service-level
objective. Hard regression thresholds should be set only after repeated
measurements on a controlled runner show the natural variance of each
benchmark.

## Measurement method

Use `pyperf` for Python microbenchmarks and small component benchmarks. It
provides calibrated worker processes, warmups, run metadata, JSON results, and
same-host comparisons. Larger end-to-end and service benchmarks may use a
separate harness, but must follow the same rules:

- record commit, Python version, dependency lock digest, CPU, memory, operating
  system, storage type, and benchmark corpus digest;
- measure outside coverage, profilers, and debug logging;
- use warmups and multiple worker processes where applicable;
- retain raw results, not only a summary table;
- compare like with like on the same class of runner;
- report instability rather than hiding it with repeated cherry-picked runs;
- keep correctness assertions enabled around setup and final outputs.

Wall time alone is insufficient. Record, where relevant:

- CPU time;
- peak resident memory;
- bytes read and written;
- artifact and metadata storage amplification;
- operations or candidates per second;
- cold and warm cache behavior;
- p50 and p95 latency for repeated service operations;
- startup and clean-process replay cost.

## Corpus design

All benchmark inputs are immutable, versioned artifacts. Avoid one synthetic
payload shape that rewards a particular implementation.

The initial corpus contains:

- canonical exact values with small and very large numerators and denominators;
- shallow and deeply nested valid objects up to configured limits;
- artifact blobs near 1 KiB, 100 KiB, and 10 MiB;
- manifest graphs with zero, tens, and thousands of parent references within
  allowed limits;
- batches of 1, 32, and the v0.1 maximum of 256 candidates;
- direct witnesses and finite-enumeration certificates of several sizes;
- cold-store, deduplication-hit, and verified-cache-hit cases.

These are workload points, not public size limits. Normative parser and storage
limits are chosen in the schema and storage specifications and tested as
correctness properties.

The two reference-plugin corpora include:

- tiny hand-auditable cases;
- small exhaustive cases suitable for pull-request runs;
- medium cases that exercise nightly throughput and memory;
- false candidates with short witnesses;
- valid candidates with complete finite certificates;
- shrink traces with successful, rejected, duplicate, and cyclic proposals.

The directed-graph/path corpus is one adversarial workload, not the definition
of the kernel. The second non-graph plugin supplies a different candidate shape,
witness representation, and cost profile.

The exact public workloads are defined in the
[Mathematical scenario catalog](math-scenarios.md).

## v0.1 benchmark groups

### Canonical encoding and hashing

Measure:

- validate and canonicalize exact values;
- canonicalize complete artifact payloads;
- hash canonical bytes;
- decode and verify stored bytes;
- rejection cost for over-limit and malformed objects.

Report throughput by canonical byte and by object. Keep validation and hashing
as separate sub-benchmarks so an optimization cannot silently remove a required
check.

### Artifact store

Measure:

- cold `artifact.put`;
- duplicate `artifact.put`;
- manifest commit and lookup;
- verified blob read;
- store reopen;
- concurrent idempotent insertion once concurrency is supported;
- garbage-collection mark traversal without deletion;
- quota-check overhead.

Report blob and SQLite write amplification as well as latency. Crash recovery is
a conformance test, not a speed benchmark.

### Checker registry and dispatch

Measure:

- compatible checker resolution;
- rejected incompatible lookup;
- authorization-policy lookup;
- cold checker process startup;
- warm dispatch;
- verification-cache lookup.

The benchmark must execute the same binding checks as production. A
short-circuit benchmark-only path is forbidden.

### Witness and certificate replay

Measure:

- direct witness validation and replay;
- finite-enumeration certificate parsing;
- per-row and total replay cost;
- clean-process verification;
- invalid-evidence rejection at early and late mutation positions.

Invalid evidence is included because adversarial inputs should be bounded.
Rejection benchmarks do not replace parser limit tests.

### Evaluation and witness orchestration

Measure:

- fixed-overhead batch dispatch for 1, 32, and 256 trivial candidates;
- result-envelope construction and artifact persistence;
- mixed batches with accepted, rejected, timed-out, and errored items;
- cold and warm evaluation-cache behavior;
- proposed witness persistence by URI.

Report orchestration overhead separately from plugin evaluation time. This
shows when optimizing the kernel matters and when domain computation dominates.

### Shrinking

Measure:

- proposal bookkeeping per reducer result;
- preservation-checker calls per accepted reduction;
- duplicate/cycle detection;
- trace persistence;
- time to reach a verified local reduction on fixed small cases;

Report the number of checker invocations and candidates considered alongside
time. A faster result produced by skipping verification is invalid.

### CLI and MCP adapter

Measure:

- installed CLI startup;
- local MCP stdio startup;
- one small structured request;
- batch request encoding and decoding;
- resource-handle response construction.

Adapter benchmarks compare their overhead with direct Python API calls. They
must not embed large artifacts simply to improve apparent resource-read
latency.

## Correctness benchmarks

The reference episodes in [Reference benchmarks](benchmarks.md) are
pass/fail research benchmarks, not performance contests. Track:

- whether the hidden semantic object is found;
- whether its witness independently verifies;
- whether corrupted and rebound evidence is rejected;
- whether the verified example replays in a clean process;
- whether shrinking reports an honest minimality level without trusting an
  empty reducer response;
- whether both domains use the same kernel contracts.

Runtime and resource use may be reported secondarily. Correctness is the gate.

The initial executable harness covers canonical rational encoding,
deduplicated artifact insertion, and verified artifact reads:

```sh
uv run python benchmarks/benchmark_v01.py
```

Use pyperf's ordinary CLI flags to select a faster development run or write raw
JSON. These measurements are baselines only; no timing threshold is a v0.1
release gate.

## Later-release benchmark groups

### v0.2 — Bounded discovery

Measure:

- raw and isomorphism-reduced candidates per second;
- canonicalization cache hit rate and cost;
- enumeration checkpoint and resume overhead;
- exact separator and projection cost by dimension and generator count;
- transformation proposal and verification cost separately.

Enumeration benchmarks always report the exact declared scope and number of
unique canonical objects. Throughput without scope correctness is meaningless.

### v0.3 — Scalable search

Measure:

- candidates evaluated per worker-second;
- queue and persistence overhead;
- archive insertion and dominance-query cost;
- lineage storage amplification;
- checkpoint, cancellation, crash recovery, and resume time;
- duplicate work under worker failure;
- local worker cold start, warm start, and process-limit overhead;
- single-process versus multi-process scaling efficiency.

Establish a correct sequential reference run before interpreting parallel
speedups.

### v0.4 — Research memory

Measure:

- ingestion throughput and storage per experiment;
- exact filter, structural, formula, and text retrieval latency;
- index refresh and retention-policy cost;
- deduplication and curated-promotion overhead;
- held-out retrieval quality, not just query speed.

Quality metrics must be computed separately by trust label and temporal cutoff.

### v0.5 — Conjecture development

Measure:

- falsification throughput for generated hypotheses;
- duplicate and near-duplicate filtering cost;
- parameter-region proposal and certificate replay cost;
- verified yield per compute budget.

No count of generated conjectures is meaningful without novelty, falsification,
and trust labels.

### v1.0 — Reproducibility

Measure:

- bundle export size and time;
- offline integrity verification;
- clean-install checker resolution;
- full independent replay time;
- compatibility migration cost.

## Regression policy

During initial development, performance jobs publish trends but do not fail
pull requests. A benchmark becomes a gate only when:

1. its correctness behavior is already covered elsewhere;
2. its corpus and harness have stable immutable identities;
3. at least ten controlled baseline runs characterize variance;
4. the project has documented why regression in that metric matters;
5. the threshold is larger than ordinary run-to-run noise.

Potential regressions are confirmed on a controlled runner against the exact
base and candidate commits. A single noisy shared-CI result is not sufficient.
Absolute memory, output, and resource limits are different: those are
correctness and availability gates from the moment the limit is specified.

Raw benchmark JSON and corpus digests should be retained as build artifacts.
Only curated summaries belong in long-lived documentation.
