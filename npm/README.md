# jacobian

A thin Node launcher and MCP client installer for
[Jacobian](https://github.com/morluto/jacobian) — the verifier-centric MCP
workbench for bounded, executable mathematics.

This package does not implement the kernel itself. It bootstraps the Python
distribution (`jacobian-research-kernel`) and provides commands to register
Jacobian with MCP clients, verify the handshake, and forward to the full CLI.

## Requirements

- Node.js >= 18
- Python 3.12 and `uv` on `$PATH` (the launcher installs the kernel on first
  use via `uvx`/`uv tool`)

## Install

```sh
npm install -g jacobian
```

## Usage

```sh
jacobian setup [--client <id>...] [--all] [--yes] [--dry-run] [--json]
  Configure MCP clients to use Jacobian.
jacobian doctor [--json]
  Verify the MCP handshake and tool catalog.
jacobian remove [--client <id>...] [--all] [--yes] [--json]
  Remove Jacobian from MCP client configs.
jacobian mcp
  Run the Jacobian MCP server over stdio.
jacobian <command> [args...]
  Forward to the Python Jacobian CLI.
```

Supported clients: `claude`, `cursor`, `opencode`, `codex`, `gemini`.

## Environment

- `JACOBIAN_STATE_DIR` — state directory (default: `./.jacobian`)
- `JACOBIAN_PACKAGE` — Python package spec (default: `jacobian-research-kernel`)

## Verification model

Search and evaluation may be wrong. A result becomes verified only when an
operator-authorized checker accepts evidence bound to the exact claim,
semantics, candidate, and checker version. This launcher never promotes
evaluator output or solver status to a verified conclusion.

## License

MIT
