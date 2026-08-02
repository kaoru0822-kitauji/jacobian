# Harbor source adapters

This directory is reserved for reproducible conversions from pinned external
benchmark sources into task bundles under the owning
`benchmarks/datasets/<dataset>/` Harbor dataset root. An
adapter must record the immutable source revision and content digest, license
and redistribution status, included and excluded rows, deterministic conversion
command, pinned dependencies, Oracle evidence, and parity evidence when it
claims equivalence to the source.

Manually authored or substantially transformed tasks remain authored Harbor
tasks with provenance metadata; an “inspired by” citation is not an adapter.

Each adapter directory must contain `source.lock.json`, `generate.py`, and an
executable `check.sh`. The lock conforms to
`benchmarks/schemas/source-adapter-lock.schema.json` and binds source revision,
license, row selection, dependencies, output task digests, Oracle evidence,
and parity evidence. `make harbor-check` validates every lock without network
access; `make harbor-adapter-check ADAPTER=<id>` additionally runs that
adapter's deterministic regeneration check.
