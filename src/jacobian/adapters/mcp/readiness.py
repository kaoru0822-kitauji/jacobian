"""Read-only readiness probe for container-local Jacobian MCP sidecars."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp_types import TextContent, TextResourceContents

EXPECTED_TOOLS = frozenset(
    {
        "capability.describe",
        "capability.invoke",
        "workspace.open",
        "workspace.query",
        "workspace.write",
    }
)


async def inspect_once(url: str, *, required_capability: str) -> dict[str, Any]:
    """Initialize MCP and check the read-only surface needed by observations."""

    async with (
        httpx2.AsyncClient(trust_env=False, timeout=10.0) as http,
        Client(
            streamable_http_client(url, http_client=http),
            raise_exceptions=True,
        ) as client,
    ):
        listed = await client.list_tools()
        tool_names = {tool.name for tool in listed.tools}
        if tool_names != EXPECTED_TOOLS:
            raise RuntimeError(
                "unexpected MCP tool surface: "
                f"expected {sorted(EXPECTED_TOOLS)}, got {sorted(tool_names)}"
            )

        catalog_result = await client.read_resource("capability://catalog")
        if not catalog_result.contents or not isinstance(
            catalog_result.contents[0], TextResourceContents
        ):
            raise RuntimeError("capability catalog is not a text resource")
        catalog = json.loads(catalog_result.contents[0].text)
        capability_ids = {
            item["capability_id"]
            for item in catalog.get("capabilities", [])
            if isinstance(item, dict) and isinstance(item.get("capability_id"), str)
        }
        if required_capability not in capability_ids:
            raise RuntimeError(f"required capability is absent: {required_capability}")

        description_result = await client.call_tool(
            "capability.describe",
            {"capability_id": required_capability},
        )
        if description_result.is_error or not description_result.content:
            raise RuntimeError("required capability description failed")
        description = description_result.content[0]
        if not isinstance(description, TextContent):
            raise RuntimeError("required capability description is not text")
        payload = json.loads(description.text)
        capability = payload.get("capability")
        if (
            not isinstance(capability, dict)
            or capability.get("capability_id") != required_capability
        ):
            raise RuntimeError("required capability description is inconsistent")

        server_info = client.server_info
        if server_info is None:
            raise RuntimeError("MCP initialization returned no server identity")

        return {
            "server": {
                "name": server_info.name,
                "version": server_info.version,
            },
            "tool_names": sorted(tool_names),
            "catalog": {
                "capability_count": len(capability_ids),
                "policy_profile": catalog.get("policy_profile"),
                "policy_digest": catalog.get("policy_digest"),
            },
            "required_capability": required_capability,
        }


async def wait_until_ready(
    url: str,
    *,
    required_capability: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Retry the complete read-only probe until success or a bounded timeout."""

    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return await inspect_once(url, required_capability=required_capability)
        except Exception as exc:  # readiness must retry transport and startup errors
            last_error = exc
        remaining = deadline - time.monotonic()
        if remaining > 0:
            await asyncio.sleep(min(1.0, remaining))
    detail = f": {last_error}" if last_error is not None else ""
    raise RuntimeError(f"Jacobian MCP did not become ready{detail}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--require-capability", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.timeout_seconds <= 0:
        raise SystemExit("--timeout-seconds must be positive")
    try:
        report = asyncio.run(
            wait_until_ready(
                args.url,
                required_capability=args.require_capability,
                timeout_seconds=args.timeout_seconds,
            )
        )
    except RuntimeError as exc:
        raise SystemExit(f"readiness failed: {exc}") from None
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["EXPECTED_TOOLS", "inspect_once", "wait_until_ready"]
