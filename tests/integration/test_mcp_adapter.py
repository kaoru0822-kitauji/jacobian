from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from jacobian.adapters.mcp.server import (
    _public_tool_error,
    create_server,
)

MCP_TOOL_NAMES = {"capability.describe", "capability.invoke"}


@pytest.mark.integration
def test_mcp_exposes_only_capability_tools_and_read_only_resources(
    tmp_path: Path,
) -> None:
    server = create_server(tmp_path)
    assert server.instructions is not None
    assert "assurance level VERIFIED" in server.instructions

    async def scenario() -> None:
        from mcp import Client

        async with Client(server, raise_exceptions=True) as client:
            listed = await client.list_tools()
            tools = {tool.name: tool for tool in listed.tools}
            assert set(tools) == MCP_TOOL_NAMES
            assert all(
                tool.annotations is not None
                and tool.annotations.open_world_hint is False
                for tool in tools.values()
            )
            assert tools["capability.describe"].annotations is not None
            assert tools["capability.describe"].annotations.read_only_hint is True

            catalog_result = await client.read_resource("capability://catalog")
            catalog = json.loads(catalog_result.contents[0].text)
            capability_ids = {
                descriptor["capability_id"] for descriptor in catalog["capabilities"]
            }
            assert "knowledge.search" in capability_ids
            assert "lean.check" in capability_ids

            reference_result = await client.read_resource("reference://catalog")
            references = json.loads(reference_result.contents[0].text)
            assert references["matrices"]["plugin_id"].startswith("artifact://sha256/")

    asyncio.run(scenario())


@pytest.mark.integration
def test_mcp_describes_and_invokes_capabilities(tmp_path: Path) -> None:
    async def scenario() -> None:
        from mcp import Client

        async with Client(create_server(tmp_path), raise_exceptions=True) as client:
            described = await client.call_tool(
                "capability.describe", {"capability_id": "knowledge.search"}
            )
            contract = json.loads(described.content[0].text)
            assert contract["capability"]["capability_id"] == "knowledge.search"

            result = await client.call_tool(
                "capability.invoke",
                {
                    "capability_id": "knowledge.search",
                    "mode": "EXPLORE",
                    "payload": {"query": "counterexample", "limit": 5},
                },
            )
            response = json.loads(result.content[0].text)
            assert response["execution"]["status"] == "COMPLETED"
            assert response["assurance"]["level"] == "COMPUTED"

            unknown = await client.call_tool(
                "capability.invoke",
                {
                    "capability_id": "missing.capability",
                    "mode": "EXPLORE",
                    "payload": {},
                },
            )
            unknown_result = json.loads(unknown.content[0].text)
            assert unknown.is_error is False
            assert unknown_result["output"]["error"]["code"] == "UNKNOWN_CAPABILITY"

    asyncio.run(scenario())


@pytest.mark.integration
def test_mcp_tool_failures_return_safe_actionable_errors(tmp_path: Path) -> None:
    async def scenario() -> None:
        from mcp import Client

        async with Client(create_server(tmp_path), raise_exceptions=False) as client:
            unknown_capability = await client.call_tool(
                "capability.describe", {"capability_id": "missing.capability"}
            )
            response = json.loads(unknown_capability.content[0].text)
            assert response["error"]["code"] == "UNKNOWN_CAPABILITY"
            assert "list installed capabilities" in response["error"]["hint"]

    asyncio.run(scenario())

    internal = json.loads(_public_tool_error("fixture", KeyError("internal")))
    assert internal["error"]["code"] == "OPERATION_FAILED"


@pytest.mark.integration
def test_mcp_protocol_and_authentication_errors_remain_distinct(tmp_path: Path) -> None:
    from mcp.shared.exceptions import MCPError

    server = create_server(tmp_path)

    @server.tool(name="fixture.protocol-error")
    async def protocol_error() -> None:
        raise MCPError(123, "protocol action required")

    with pytest.raises(MCPError, match="protocol action required"):
        asyncio.run(server.call_tool("fixture.protocol-error", {}))

    async def scenario() -> None:
        from mcp import Client

        async with Client(
            create_server(
                tmp_path,
                tenant_isolation=True,
                allow_anonymous=False,
            ),
            raise_exceptions=False,
        ) as client:
            response = await client.call_tool("capability.describe", {})
            assert response.is_error is True
            assert '"code": "AUTHENTICATION_REQUIRED"' in response.content[0].text

    asyncio.run(scenario())


@pytest.mark.integration
@pytest.mark.subprocess
def test_mcp_stdio_entrypoint_exposes_only_capability_tools(tmp_path: Path) -> None:
    async def scenario() -> None:
        from mcp import Client, StdioServerParameters, stdio_client

        environment = dict(os.environ)
        environment["JACOBIAN_STATE_DIR"] = str(tmp_path)
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "jacobian.adapters.mcp.server"],
            env=environment,
            cwd=Path.cwd(),
        )
        async with Client(
            stdio_client(parameters),
            raise_exceptions=True,
        ) as client:
            listed = await client.list_tools()
            assert {tool.name for tool in listed.tools} == MCP_TOOL_NAMES

    asyncio.run(scenario())


@pytest.mark.integration
@pytest.mark.subprocess
def test_mcp_entrypoint_has_nonstarting_help() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "jacobian.adapters.mcp.server", "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )

    assert completed.returncode == 0
    assert "Run the Jacobian MCP server" in completed.stdout
    assert "--tool-profile" not in completed.stdout
