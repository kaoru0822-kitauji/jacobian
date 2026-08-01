# Harbor source adapters

This directory is reserved for reproducible conversions from pinned external
benchmark sources into canonical `benchmarks/tasks/<task-id>/` bundles. An
adapter must record the immutable source revision and content digest, license
and redistribution status, included and excluded rows, deterministic conversion
command, pinned dependencies, Oracle evidence, and parity evidence when it
claims equivalence to the source.

Manually authored or substantially transformed tasks remain authored Harbor
tasks with provenance metadata; an “inspired by” citation is not an adapter.
