# Harbor task template

Copy this directory into a registered dataset and replace every placeholder.
Keep `instruction.md` and `environment/` agent-visible; keep `solution/` and
`tests/` Oracle/verifier-only. Add task-specific schemas without weakening the
common submission envelope or assurance ceiling. Run `make harbor-sync` to
vendor the repository-owned `benchmarks/tooling/verifier_support.py` into the
task's verifier bundle and to generate its Harbor digest.
