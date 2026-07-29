"""Start a local Jacobian MCP server with a frozen evaluation ablation."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from jacobian.adapters.mcp.server import create_server
from jacobian.capabilities import CapabilityPolicy, CapabilityPolicyProfile


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--exclude-capability", action="append", default=[])
    parser.add_argument(
        "--capability-policy-profile",
        choices=("DEFAULT", "COMPUTE_VERIFY_NO_RETRIEVAL"),
        default="DEFAULT",
    )
    args = parser.parse_args(argv)
    policy_profile = cast(
        CapabilityPolicyProfile,
        args.capability_policy_profile,
    )
    create_server(
        state_dir=args.state_dir,
        capability_exclusions=frozenset(args.exclude_capability),
        capability_policy=CapabilityPolicy(profile=policy_profile),
    ).run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
