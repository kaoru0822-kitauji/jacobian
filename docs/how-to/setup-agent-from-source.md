# Configure an agent from a source checkout

Use the source bootstrap when an agent must run the exact code in a Jacobian
clone rather than the latest published Python package. From the repository
root, run:

```sh
./scripts/setup-agent --client codex --profile full-python --yes
```

Replace `codex` with `claude`, `cursor`, `gemini`, or `opencode`; repeat
`--client` to configure several clients, or use `--all`. The generated client
entry starts the server directly from the absolute clone and state paths:

```text
uv run --project /absolute/path/to/jacobian --locked --no-sync \
  jacobian-mcp --state-dir /absolute/path/to/jacobian/.jacobian
```

The bootstrap requires the uv version in [`.uv-version`](../../.uv-version),
Python 3.12 or 3.13, Git, and Node.js 18 or newer. It requires a clean checkout,
performs a locked sync, initializes the state directory, and audits the exact
Git revision, package version, catalog digest, and provider runtimes before it
writes any client configuration. The audit is saved as
`.jacobian/bootstrap-doctor.json` unless `--state-dir` selects another path.
The generated launcher preserves the provider-bearing base `PATH` used by
doctor. uv prepends the project virtual environment to that same base path for
both doctor and MCP, so GUI clients resolve the same Lean and external-proof
executables that were audited in the terminal. If the bootstrap inherits a
custom `UV_PROJECT_ENVIRONMENT`, it resolves that path absolutely and records
it in the launcher. The `lean` profile likewise records a nondefault
`ELAN_HOME` and any `JACOBIAN_LEAN_RUNTIME` override, so a GUI restart uses the
toolchain home and mathlib checkout that doctor audited.

## Profiles

| Profile | Installed or checked surface |
| --- | --- |
| `core` | Locked base dependencies, including SymPy and Z3 |
| `full-python` | `core` plus all maintained Python extras: python-flint and cvc5 |
| `lean` | `full-python` plus a build of the pinned `lean/lean-toolchain` project; `elan`/`lake` must already be on `PATH` |
| `external-proof` | `full-python` plus fail-closed availability checks for pinned CaDiCaL, DRAT-trim, and Carcara executables |

The `external-proof` profile does not download or trust native executables on
the user's behalf. Their exact version and provenance contracts are defined in
the [SAT artifact reference](../reference/sat-artifacts.md) and
[SMT artifact reference](../reference/smt-artifacts.md). If a required provider
is absent or has the wrong identity, doctor fails before client configuration.
The `lean` profile likewise uses the repository's pinned toolchain and manifest
instead of a floating Lean installation.

Add `--dev` when the clone also needs the locked development group. Use
`--dry-run` to inspect every sync, init, configuration, and doctor command
without changing the environment, state directory, or client files. Repeating
the same command is idempotent. Client edits are one transaction: if any write
fails, all earlier files from that run are restored. `jacobian remove` removes
only the Jacobian entry and preserves unrelated client settings. Client config
symlinks are rejected rather than replaced; update the link target directly or
temporarily use a regular config file.

After pulling a new commit, rerun the bootstrap. The client already points at
the same source path, while the locked sync and doctor refresh its environment
and recorded identity before the next agent session.
