"""Start a local Jacobian MCP server with a frozen evaluation ablation."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from jacobian.adapters.mcp.server import create_server


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--exclude-capability", action="append", default=[])
    args = parser.parse_args(argv)
    create_server(
        state_dir=args.state_dir,
        capability_exclusions=frozenset(args.exclude_capability),
    ).run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
