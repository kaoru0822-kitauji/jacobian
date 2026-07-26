from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from jacobian.adapters.mcp.server import (
    WORKSPACE_TOOL_NAMES,
    _public_tool_error,
    create_server,
)

CAPABILITY_TOOL_NAMES = {"capability.describe", "capability.invoke"}
MCP_TOOL_NAMES = CAPABILITY_TOOL_NAMES | WORKSPACE_TOOL_NAMES


@pytest.mark.integration
def test_mcp_exposes_capability_and_workspace_tools_with_read_only_resources(
    tmp_path: Path,
) -> None:
    server = create_server(tmp_path)
    assert server.instructions is not None
    assert "assurance level VERIFIED" in server.instructions
    assert "workspace entry never promotes" in server.instructions

    async def scenario() -> None:
        from mcp import Client

        async with Client(server, raise_exceptions=True) as client:
            listed = await client.list_tools()
            tools = {tool.name: tool for tool in listed.tools}
            assert set(tools) == MCP_TOOL_NAMES
            descriptor = json.dumps(
                {
                    "instructions": server.instructions,
                    "tools": [tool.model_dump(mode="json") for tool in listed.tools],
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            assert len(descriptor) < 25_000
            assert all(
                tool.annotations is not None
                and tool.annotations.open_world_hint is False
                for tool in tools.values()
            )
            assert tools["capability.describe"].annotations is not None
            assert tools["capability.describe"].annotations.read_only_hint is True
            assert tools["workspace.open"].annotations is not None
            assert tools["workspace.open"].annotations.idempotent_hint is True
            assert tools["workspace.write"].annotations is not None
            assert tools["workspace.write"].annotations.idempotent_hint is True
            assert tools["workspace.query"].annotations is not None
            assert tools["workspace.query"].annotations.read_only_hint is True
            assert all(
                tools[name].output_schema is None for name in WORKSPACE_TOOL_NAMES
            )

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
def test_mcp_workspace_schema_aliases_and_fail_closed_round_trip(
    tmp_path: Path,
) -> None:
    server = create_server(tmp_path)

    async def scenario() -> None:
        from mcp import Client

        async with Client(server, raise_exceptions=True) as client:
            listed = await client.list_tools()
            tools = {tool.name: tool for tool in listed.tools}
            open_schema = tools["workspace.open"].input_schema
            write_tool = tools["workspace.write"]
            write_schema = write_tool.input_schema
            query_schema = tools["workspace.query"].input_schema

            assert open_schema["properties"]["idempotency_key"]["pattern"] == (
                "^[A-Za-z0-9._:-]{8,128}$"
            )
            assert open_schema["properties"]["name"]["maxLength"] == 128
            assert open_schema["properties"]["problem"]["maxLength"] == 16_384
            assert open_schema["properties"]["tags"]["anyOf"][0]["maxItems"] == 16
            assert write_tool.description is not None
            assert "base_revision (never revision_id)" in write_tool.description
            assert "never a batch wrapper" in write_tool.description
            assert "client_ref, never ref" in write_tool.description
            assert "never depends_on_refs" in write_tool.description
            assert write_schema["additionalProperties"] is False
            write_properties = write_schema["properties"]
            assert write_properties["workspace_id"]["pattern"] == (
                "^workspace://[0-9a-f]{32}$"
            )
            assert write_properties["branch_id"]["pattern"] == (
                "^branch://[0-9a-f]{32}$"
            )
            assert write_properties["base_revision"]["pattern"] == (
                "^revision://[0-9a-f]{32}$"
            )
            for field_name in ("scratch", "findings", "attempts", "marks"):
                assert write_properties[field_name]["anyOf"][0]["maxItems"] == 64
            assert query_schema["properties"]["limit"]["minimum"] == 1
            assert query_schema["properties"]["limit"]["maximum"] == 50
            assert query_schema["properties"]["workspace_id"]["pattern"] == (
                "^workspace://[0-9a-f]{32}$"
            )
            assert (
                query_schema["properties"]["target_card_id"]["anyOf"][0]["pattern"]
                == "^card://[0-9a-f]{32}$"
            )

            finding_kinds = write_schema["$defs"]["WorkspaceFindingKind"]["enum"]
            attempt_outcomes = write_schema["$defs"]["WorkspaceAttemptOutcome"]["enum"]
            assert "OPEN_GOAL" in finding_kinds
            assert "PROBLEM" not in finding_kinds
            assert "SUCCEEDED" in attempt_outcomes
            mark_schema = write_schema["$defs"]["WorkspaceMarkDraft"]
            assert "summary" in mark_schema["properties"]
            assert mark_schema["oneOf"]

            alias_payload = {
                "workspace_id": "workspace://" + ("0" * 32),
                "branch_id": "branch://" + ("0" * 32),
                "base_revision": "revision://" + ("0" * 32),
                "idempotency_key": "schema-aliases-001",
                "findings": [
                    {
                        "client_ref": "G1",
                        "kind": "OPEN_GOAL",
                        "title": "Open work",
                        "body": "A documented finding-kind alias.",
                    }
                ],
                "attempts": [
                    {
                        "client_ref": "T1",
                        "target_ref": "G1",
                        "method": "direct",
                        "outcome": "SUCCEEDED",
                        "summary": "A documented attempt-outcome alias.",
                    }
                ],
                "marks": [
                    {
                        "client_ref": "M1",
                        "target_ref": "G1",
                        "state": "CLOSED",
                        "summary": "A documented mark-reason alias.",
                    }
                ],
            }
            write_validator = Draft202012Validator(write_schema)
            assert write_validator.is_valid(alias_payload), list(
                write_validator.iter_errors(alias_payload)
            )
            assert not write_validator.is_valid(
                {
                    **alias_payload,
                    "marks": [
                        {
                            "client_ref": "M1",
                            "target_ref": "G1",
                            "state": "CLOSED",
                            "reason": "Canonical reason.",
                            "summary": "Conflicting alias.",
                        }
                    ],
                }
            )
            assert not write_validator.is_valid(
                {
                    **alias_payload,
                    "findings": [
                        {
                            "client_ref": "P2",
                            "kind": "PROBLEM",
                            "title": "Hidden second problem",
                            "body": "Only workspace.open creates the problem.",
                        }
                    ],
                    "attempts": [],
                    "marks": [],
                }
            )

            misdirected_result = await client.call_tool(
                "capability.describe",
                {"capability_id": "workspace.write"},
            )
            misdirected = json.loads(misdirected_result.content[0].text)
            assert misdirected["error"]["code"] == "UNKNOWN_CAPABILITY"
            assert "direct MCP tool" in misdirected["error"]["hint"]

            opened_result = await client.call_tool(
                "workspace.open",
                {
                    "idempotency_key": "mcp-workspace-open-001",
                    "name": "MCP workspace",
                    "problem": "Record a goal and one completed attempt.",
                },
            )
            opened = json.loads(opened_result.content[0].text)

            rejected_result = await client.call_tool(
                "workspace.write",
                {
                    "idempotency_key": "mcp-workspace-unknown-field-001",
                    "workspace_id": opened["workspace_id"],
                    "branch_id": opened["branch_id"],
                    "base_revision": opened["revision_id"],
                    "cards": [],
                    "attempts": [
                        {
                            "client_ref": "T0",
                            "target_ref": opened["problem_card_id"],
                            "method": "must-not-commit",
                            "outcome": "COMPLETED",
                            "summary": "Unknown input rejects the entire write.",
                        }
                    ],
                },
            )
            assert rejected_result.is_error is True

            second_problem_result = await client.call_tool(
                "workspace.write",
                {
                    "idempotency_key": "mcp-workspace-second-problem-001",
                    "workspace_id": opened["workspace_id"],
                    "branch_id": opened["branch_id"],
                    "base_revision": opened["revision_id"],
                    "findings": [
                        {
                            "client_ref": "P2",
                            "kind": "PROBLEM",
                            "title": "Hidden second problem",
                            "body": "Only workspace.open creates the problem.",
                        }
                    ],
                },
            )
            assert second_problem_result.is_error is True

            unchanged_result = await client.call_tool(
                "workspace.query",
                {
                    "workspace_id": opened["workspace_id"],
                    "branch_id": opened["branch_id"],
                    "revision_id": opened["revision_id"],
                    "view": "RESUME",
                },
            )
            unchanged = json.loads(unchanged_result.content[0].text)
            assert unchanged["revision_id"] == opened["revision_id"]
            assert unchanged["resume"]["recent_attempts"] == []

            write_result = await client.call_tool(
                "workspace.write",
                {
                    "idempotency_key": "mcp-workspace-write-001",
                    "workspace_id": opened["workspace_id"],
                    "branch_id": opened["branch_id"],
                    "base_revision": opened["revision_id"],
                    "findings": [
                        {
                            "client_ref": "A1",
                            "kind": "ASSUMPTION",
                            "title": "Temporary scope",
                            "body": "Assume a temporary finite scope.",
                        },
                        {
                            "client_ref": "G1",
                            "kind": "OPEN_GOAL",
                            "title": "MCP goal",
                            "body": "Close the remaining case.",
                            "assumption_refs": ["A1"],
                        },
                    ],
                    "attempts": [
                        {
                            "client_ref": "T1",
                            "target_ref": "G1",
                            "method": "direct",
                            "outcome": "SUCCEEDED",
                            "summary": "The operational attempt completed.",
                        }
                    ],
                    "focus": {"active_ref": "G1", "pinned_refs": ["G1"]},
                },
            )
            written = json.loads(write_result.content[0].text)
            assert written["findings_written"] == 2
            assert written["attempts_written"] == 1

            conflicting_mark_result = await client.call_tool(
                "workspace.write",
                {
                    "idempotency_key": "mcp-workspace-mark-conflict-001",
                    "workspace_id": opened["workspace_id"],
                    "branch_id": opened["branch_id"],
                    "base_revision": written["revision_id"],
                    "marks": [
                        {
                            "client_ref": "M0",
                            "target_ref": written["id_map"]["A1"],
                            "state": "RETRACTED",
                            "reason": "Canonical reason.",
                            "summary": "Conflicting alias.",
                        }
                    ],
                },
            )
            assert conflicting_mark_result.is_error is True

            mark_result = await client.call_tool(
                "workspace.write",
                {
                    "idempotency_key": "mcp-workspace-mark-001",
                    "workspace_id": opened["workspace_id"],
                    "branch_id": opened["branch_id"],
                    "base_revision": written["revision_id"],
                    "marks": [
                        {
                            "client_ref": "M1",
                            "target_ref": written["id_map"]["A1"],
                            "state": "RETRACTED",
                            "summary": "The temporary scope was withdrawn.",
                        }
                    ],
                },
            )
            marked = json.loads(mark_result.content[0].text)
            assert marked["marks_written"] == 1

            context_result = await client.call_tool(
                "workspace.query",
                {
                    "workspace_id": opened["workspace_id"],
                    "branch_id": opened["branch_id"],
                    "revision_id": marked["revision_id"],
                    "view": "CONTEXT",
                    "target_card_id": written["id_map"]["G1"],
                },
            )
            context = json.loads(context_result.content[0].text)["context"]
            assert context["target"]["kind"] == "GOAL"
            assert context["target"]["stale"] is True
            assert context["target"]["stale_due_to_ids"] == [written["id_map"]["A1"]]
            assert context["target"]["verification"] == "UNVERIFIED"
            assert context["dependencies"][0]["state"] == "RETRACTED"
            assert context["recent_attempts"][0]["outcome"] == "COMPLETED"
            assert context["recent_attempts"][0]["verification"] == "UNVERIFIED"

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
def test_mcp_stdio_entrypoint_exposes_capability_and_workspace_tools(
    tmp_path: Path,
) -> None:
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
