# Jacobian public-reproductions-v1

This Harbor dataset contains independently verifiable public mathematical cases.
Each case is a self-contained task directly under this dataset directory;
public provenance does not
make Oracle solutions or verifier code agent-visible.

`suite.toml` is the source of truth for membership and task contract metadata.
`dataset.toml` is generated from Harbor task digests and must not be edited by
hand. The Oracle job runs every migrated case:

```sh
make harbor-oracle DATASET=public-reproductions-v1
```

These tasks establish deterministic public-case correctness. They are not a
held-out performance split and their rewards must not be compared with the
workflow, diagnostic, performance, provider, or example datasets.
