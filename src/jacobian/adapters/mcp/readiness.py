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

# Keep this contract aligned with the current SDK-2 server.  Workspace tools
# were retired; accepting the old surface would make a stale sidecar look
# ready while the benchmark exercised a different protocol.
EXPECTED_TOOLS = frozenset({"capability.describe", "capability.invoke"})


def _catalog_payload(
    result: Any, required_capability: str
) -> tuple[dict[str, Any], set[str]]:
    if not result.contents or not isinstance(result.contents[0], TextResourceContents):
        raise RuntimeError("capability catalog is not a text resource")
    try:
        catalog = json.loads(result.contents[0].text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("capability catalog is not valid JSON") from exc
    if not isinstance(catalog, dict):
        raise RuntimeError("capability catalog is not an object")
    capability_ids = {
        item["capability_id"]
        for item in catalog.get("capabilities", [])
        if isinstance(item, dict) and isinstance(item.get("capability_id"), str)
    }
    if required_capability not in capability_ids:
        raise RuntimeError(f"required capability is absent: {required_capability}")
    return catalog, capability_ids


def _description_payload(result: Any, required_capability: str) -> None:
    if result.is_error or not result.content:
        raise RuntimeError("required capability description failed")
    description = result.content[0]
    if not isinstance(description, TextContent):
        raise RuntimeError("required capability description is not text")
    try:
        payload = json.loads(description.text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("required capability description is not valid JSON") from exc
    capability = payload.get("capability") if isinstance(payload, dict) else None
    if (
        not isinstance(capability, dict)
        or capability.get("capability_id") != required_capability
    ):
        raise RuntimeError("required capability description is inconsistent")


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
        catalog, capability_ids = _catalog_payload(catalog_result, required_capability)

        description_result = await client.call_tool(
            "capability.describe",
            {"capability_id": required_capability},
        )
        _description_payload(description_result, required_capability)

        server_info = client.server_info
        if server_info is None:
            raise RuntimeError("MCP initialization returned no server identity")

        return {
            "server": {"name": server_info.name, "version": server_info.version},
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

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            detail = f": {last_error}" if last_error is not None else ""
            raise RuntimeError(f"Jacobian MCP did not become ready{detail}")
        try:
            # Bound the probe itself as well as the retry loop.  A transport
            # timeout must not silently extend the advertised readiness wait.
            return await asyncio.wait_for(
                inspect_once(url, required_capability=required_capability),
                timeout=remaining,
            )
        except Exception as exc:  # readiness retries transport and startup errors
            last_error = exc
        remaining = deadline - time.monotonic()
        if remaining > 0:
            await asyncio.sleep(min(1.0, remaining))


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
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(f"readiness failed: {exc}") from None
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["EXPECTED_TOOLS", "inspect_once", "wait_until_ready"]
