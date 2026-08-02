"""Executable conformance checks for the pinned MCP Python SDK boundary."""

from __future__ import annotations

import asyncio
import importlib.metadata
import json
from pathlib import Path

import pytest
from mcp.server.extension import Extension, ResourceBinding, ToolBinding
from mcp_types import CallToolResult, ResourceLink, TextContent

from jacobian.adapters.mcp.server import JacobianCoreExtension, create_server


def test_mcp_sdk_is_exactly_pinned_and_v2_bindings_are_used() -> None:
    assert importlib.metadata.version("mcp") == "2.0.0"
    assert importlib.metadata.version("mcp-types") == "2.0.0"

    extension = JacobianCoreExtension(None, None)
    assert isinstance(extension, Extension)
    assert extension.identifier == "io.jacobian/core"
    assert extension.settings() == {"version": "1"}
    assert all(isinstance(binding, ToolBinding) for binding in extension.tools())
    assert all(
        isinstance(binding, ResourceBinding) for binding in extension.resources()
    )
    assert tuple(binding.kwargs["name"] for binding in extension.tools()) == (
        "capability.describe",
        "capability.invoke",
    )


def test_mcp_v2_static_validation_context_errors_and_structured_resources(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        from mcp import Client
        from mcp.shared.exceptions import MCPError

        async with Client(create_server(tmp_path), raise_exceptions=True) as client:
            listed = await client.list_tools()
            assert all(
                tool.input_schema.get("additionalProperties") is False
                for tool in listed.tools
            )

            unknown = await client.call_tool(
                "capability.describe", {"unknown_key": "rejected"}
            )
            assert isinstance(unknown, CallToolResult)
            assert unknown.is_error is True
            assert '"code": "INVALID_INPUT"' in unknown.content[0].text

            result = await client.call_tool(
                "capability.invoke",
                {
                    "capability_id": "integer.compute.gcd",
                    "mode": "EXPLORE",
                    "payload": {"left": "84", "right": "30"},
                },
            )
            assert isinstance(result.structured_content, dict)
            link = next(
                block for block in result.content if isinstance(block, ResourceLink)
            )
            resource = await client.read_resource(link.uri)
            assert json.loads(resource.contents[0].text)["artifact_uri"] == str(
                link.uri
            )

            with pytest.raises(MCPError):
                await client.read_resource("artifact://sha256/" + "f" * 64)

    asyncio.run(scenario())


def test_mcp_types_application_failures_are_call_tool_results() -> None:
    result = CallToolResult(
        content=[TextContent(type="text", text="application failure")],
        is_error=True,
    )
    assert result.is_error is True
    assert result.content[0].text == "application failure"
