# Source catalog contract

This directory contains committed metadata and extraction recipes, not raw
repositories or dataset payloads.

- `sources.json` is the versioned source catalog and stable `source_id` list.
- `source-lock.json` binds resolved provenance, immutable revisions, licenses,
  configurations, splits, and content identities.
- `handler-probes*.json` records normalized acquisition and schema probes.
- `source-relations.json` records explicit relationships between catalog entries.
- `recipes/` records reproducible extraction or adapter inputs.

Raw snapshots and Dataset Viewer pages belong in the ignored cache. A cached
payload is reusable only when its digest, immutable upstream revision,
configuration, and split all match. Committed reports must not contain
machine-local paths, credentials, or raw restricted payloads.

Coverage labels have distinct meanings:

- **upstream reproduction**: a task faithfully instantiates an admissible
  upstream row or artifact;
- **authored family task**: a meaningful manual task represents the source
  family without claiming to reproduce an unavailable upstream instance;
- **source reference**: provenance only, and insufficient for the coverage gate.

Access and publication state are separate from coverage. Public, gated,
internal-only, unavailable, moved, or archived sources remain explicit, and
non-publishable inputs must never enter an agent-visible or publishable bundle.
The compiler and generated manifest are authoritative for per-task coverage and
redistribution decisions.
