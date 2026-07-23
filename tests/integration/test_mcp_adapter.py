from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters, stdio_client

from jacobian.adapters.mcp.server import create_server


@pytest.mark.integration
def test_mcp_exposes_exact_v01_tool_surface_and_artifact_resources(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        async with Client(
            create_server(tmp_path),
            raise_exceptions=True,
        ) as client:
            listed = await client.list_tools()
            assert {tool.name for tool in listed.tools} == {
                "artifact.put",
                "claim.validate",
                "evaluate.batch",
                "witness.find",
                "witness.verify",
                "shrink.run",
                "certificate.verify",
            }
            catalog_result = await client.read_resource("reference://catalog")
            catalog = json.loads(catalog_result.contents[0].text)
            matrix = catalog["matrices"]
            stored = await client.call_tool(
                "artifact.put",
                {
                    "schema_uri": matrix["candidate_schema_uri"],
                    "semantics_uri": matrix["semantics_uri"],
                    "payload": {
                        "rows": 1,
                        "cols": 1,
                        "entries": [["1"]],
                    },
                },
            )
            assert stored.is_error is False
            artifact_uri = stored.structured_content["artifact_uri"]
            read_back = await client.read_resource(artifact_uri)
            payload = json.loads(read_back.contents[0].text)
            assert payload["payload"]["entries"] == [["1"]]

    asyncio.run(scenario())


@pytest.mark.integration
@pytest.mark.subprocess
def test_mcp_stdio_entrypoint_starts_in_a_clean_process(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
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
            assert "certificate.verify" in {tool.name for tool in listed.tools}

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
