from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from jacobian.adapters.mcp.server import create_server

# Keep MCP SDK imports inside scenarios. Every xdist worker collects this module,
# while only workers assigned these integration tests need the expensive runtime.


@pytest.mark.integration
def test_mcp_exposes_v02_tool_surface_and_persistent_resources(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        from mcp import Client

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
                "structure.canonicalize",
                "search.enumerate",
                "search.run",
                "experiment.cancel",
                "experiment.pause",
                "experiment.resume",
                "conjecture.repair",
                "conjecture.generate",
                "parameter.generalize",
                "parameter.region.promote",
                "transform.apply",
                "transform.verify",
                "polytope.separate",
            }
            catalog_result = await client.read_resource("reference://catalog")
            catalog = json.loads(catalog_result.contents[0].text)
            matrix = catalog["matrices"]
            assert catalog["finite_polytopes"]["certificate_checker_id"].startswith(
                "checker://sha256/"
            )
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

            transformed = await client.call_tool(
                "transform.apply",
                {
                    "source_uri": artifact_uri,
                    "plugin_id": matrix["plugin_id"],
                    "target_schema_uri": matrix["representation_schema_uris"][
                        "row_major"
                    ],
                    "target_semantics_uri": matrix["representation_semantics_uris"][
                        "row_major"
                    ],
                    "requested_relation": "EQUIVALENT",
                },
            )
            assert (
                transformed.structured_content["result"]["assurance"]["verification"]
                == "UNVERIFIED"
            )
            verified_transform = await client.call_tool(
                "transform.verify",
                {
                    "transformation_uri": transformed.structured_content[
                        "transformation_uri"
                    ]
                },
            )
            assert (
                verified_transform.structured_content["assurance"]["verification"]
                == "VERIFIED"
            )

            claim = await client.call_tool(
                "artifact.put",
                {
                    "schema_uri": matrix["claim_schema_uri"],
                    "semantics_uri": matrix["semantics_uri"],
                    "payload": {
                        "claim_schema_version": "1",
                        "domain_id": "jacobian.integer-matrices",
                        "domain_version": "1",
                        "semantics_uri": matrix["semantics_uri"],
                        "quantifiers": [],
                        "predicate": {
                            "name": "is_nonsingular",
                            "parameters": {},
                        },
                        "bounds": {},
                        "required_capabilities": [
                            "CandidateEnumerator",
                            "Evaluator",
                        ],
                        "correspondence_status": "UNREVIEWED",
                    },
                },
            )
            experiment = await client.call_tool(
                "search.enumerate",
                {
                    "claim_uri": claim.structured_content["artifact_uri"],
                    "plugin_id": matrix["plugin_id"],
                    "bounds": {
                        "rows": 1,
                        "cols": 1,
                        "entries": [0, 1],
                    },
                    "budget": {
                        "candidates_max": 2,
                        "wall_seconds": 10,
                        "page_size": 2,
                    },
                },
            )
            experiment_uri = experiment.structured_content["experiment_uri"]
            snapshot_result = await client.read_resource(experiment_uri)
            snapshot = json.loads(snapshot_result.contents[0].text)
            assert snapshot["experiment_uri"] == experiment_uri
            assert snapshot["verification"] == "UNVERIFIED"
            accounting_result = await client.read_resource(
                experiment_uri + "/accounting"
            )
            accounting = json.loads(accounting_result.contents[0].text)
            assert accounting["experiment_uri"] == experiment_uri
            assert accounting["verification"] == "UNVERIFIED"

    asyncio.run(scenario())


@pytest.mark.integration
@pytest.mark.subprocess
def test_mcp_stdio_entrypoint_starts_in_a_clean_process(
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
