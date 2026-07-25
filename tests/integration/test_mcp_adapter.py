from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from jacobian.adapters.mcp.server import (
    CAPABILITY_TOOL_NAMES,
    VERIFICATION_TOOL_NAMES,
    ToolProfile,
    _public_tool_error,
    create_server,
)

# Keep MCP SDK imports inside scenarios. Every xdist worker collects this module,
# while only workers assigned these integration tests need the expensive runtime.


@pytest.mark.integration
def test_mcp_exposes_v02_tool_surface_and_persistent_resources(
    tmp_path: Path,
) -> None:
    server = create_server(tmp_path)
    assert server.instructions is not None
    assert "reference://catalog" in server.instructions
    assert "assurance.verification" in server.instructions

    async def scenario() -> None:
        from mcp import Client

        async with Client(
            server,
            raise_exceptions=True,
        ) as client:
            listed = await client.list_tools()
            tools = {tool.name: tool for tool in listed.tools}
            assert set(tools) == {
                "capability.describe",
                "capability.invoke",
                "artifact.put",
                "claim.validate",
                "evaluate.batch",
                "witness.find",
                "witness.verify",
                "shrink.run",
                "certificate.verify",
                "lean.verify",
                "verification.run",
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
            assert all(
                tool.annotations is not None
                and tool.annotations.open_world_hint is False
                for tool in tools.values()
            )
            assert tools["claim.validate"].annotations is not None
            assert tools["claim.validate"].annotations.read_only_hint is True
            assert tools["artifact.put"].annotations is not None
            assert tools["artifact.put"].annotations.read_only_hint is False
            assert tools["artifact.put"].annotations.destructive_hint is False
            assert tools["artifact.put"].annotations.idempotent_hint is True
            assert tools["search.run"].annotations is not None
            assert tools["search.run"].annotations.idempotent_hint is True
            assert tools["experiment.cancel"].annotations is not None
            assert tools["experiment.cancel"].annotations.destructive_hint is True
            assert tools["evaluate.batch"].input_schema["$defs"]["EvaluationProfile"][
                "enum"
            ] == ["FAST", "EXACT_CANDIDATE"]
            assert tools["witness.find"].input_schema["$defs"]["WitnessRole"][
                "enum"
            ] == [
                "DEFEATS_CANDIDATE",
                "RESCUES_CANDIDATE",
                "SUPPORTS_CLAIM",
                "REFUTES_CLAIM",
            ]
            assert tools["transform.apply"].input_schema["$defs"][
                "TransformationRelation"
            ]["enum"] == [
                "EQUIVALENT",
                "OVER_APPROXIMATION",
                "UNDER_APPROXIMATION",
                "HEURISTIC",
            ]
            catalog_result = await client.read_resource("reference://catalog")
            catalog = json.loads(catalog_result.contents[0].text)
            matrix = catalog["matrices"]
            assert matrix["agent_contract_uri"] == "reference://domain/matrices"
            assert matrix["domain_id"] == "jacobian.integer-matrices"
            assert matrix["domain_version"] == "1"
            assert matrix["available_capabilities"] == [
                "CandidateEnumerator",
                "Evaluator",
                "Reducer",
                "SemanticEnumerator",
                "Transformer",
                "WitnessOracle",
            ]
            erdos_straus = catalog["erdos_straus"]
            assert erdos_straus["agent_contract_uri"] == (
                "reference://domain/erdos_straus"
            )
            assert erdos_straus["domain_id"] == "jacobian.erdos-straus"
            assert erdos_straus["available_capabilities"] == [
                "Evaluator",
                "WitnessOracle",
            ]
            erdos_contract_result = await client.read_resource(
                "reference://domain/erdos_straus"
            )
            erdos_contract = json.loads(erdos_contract_result.contents[0].text)
            assert set(erdos_contract["claim_contract"]["predicates"]) == {
                "erdos_straus_range"
            }
            assert erdos_contract["semantics"]["checker_identity"] == (
                "4*x*y*z = n*(x*y + x*z + y*z)"
            )
            assert catalog["finite_polytopes"]["certificate_checker_id"].startswith(
                "checker://sha256/"
            )
            assert catalog["lean4"]["certificate_type"] == "lean4.kernel"
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
def test_mcp_capability_profile_describes_and_invokes_exact_domain_contract(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        from mcp import Client

        async with Client(
            create_server(tmp_path, tool_profile=ToolProfile.CAPABILITIES),
            raise_exceptions=True,
        ) as client:
            listed = await client.list_tools()
            assert {tool.name for tool in listed.tools} == CAPABILITY_TOOL_NAMES
            assert all(tool.output_schema is None for tool in listed.tools)
            tools = {tool.name: tool for tool in listed.tools}
            assert tools["capability.describe"].annotations is not None
            assert tools["capability.describe"].annotations.read_only_hint is True

            resource = await client.read_resource("capability://catalog")
            catalog = json.loads(resource.contents[0].text)
            capability_ids = {
                descriptor["capability_id"] for descriptor in catalog["capabilities"]
            }
            assert capability_ids == {
                "graph.compute.properties",
                "graph.search.atlas",
                "knowledge.search",
                "lean.check",
                "reference.solve",
            }

            described = await client.call_tool(
                "capability.describe",
                {
                    "capability_id": "reference.solve",
                    "reference_name": "erdos_straus",
                },
            )
            contract = json.loads(described.content[0].text)
            assert contract["capability"]["capability_id"] == "reference.solve"
            assert set(contract["domain"]["claim_contract"]["predicates"]) == {
                "erdos_straus_range"
            }
            example = contract["domain"]["invocation_examples"][0]
            assert example["capability_id"] == "reference.solve"
            assert example["mode"] == "VERIFY"
            assert example["payload"]["candidate"] == {
                "lower_bound": 2,
                "upper_bound": 20,
            }
            graph_description = await client.call_tool(
                "capability.describe",
                {
                    "capability_id": "reference.solve",
                    "reference_name": "graph_paths",
                },
            )
            graph_contract = json.loads(graph_description.content[0].text)["domain"]
            assert {
                item["payload"]["predicate"]["name"]
                for item in graph_contract["invocation_examples"]
            } == set(graph_contract["claim_contract"]["predicates"])
            matrix_description = await client.call_tool(
                "capability.describe",
                {
                    "capability_id": "reference.solve",
                    "reference_name": "matrices",
                },
            )
            matrix_contract = json.loads(matrix_description.content[0].text)["domain"]
            matrix_limit = matrix_contract["verification_limits"][
                "maximize_absolute_determinant"
            ]
            assert matrix_limit["max_enumerated_candidates"] == 65536
            assert matrix_limit["scope_cardinality"] == (
                "len(entries) ** (rows * cols)"
            )
            assert matrix_limit["on_excess"] == "REJECTED_WITHOUT_CONCLUSION"
            lean_description = await client.call_tool(
                "capability.describe",
                {"capability_id": "lean.check"},
            )
            lean_contract = json.loads(lean_description.content[0].text)
            assert (
                lean_contract["runtime"]["profiles"]["CORE"]["checker_timeout_seconds"]
                == 30
            )
            assert (
                lean_contract["runtime"]["profiles"]["MATHLIB"][
                    "checker_timeout_seconds"
                ]
                == 105
            )
            assert lean_contract["cache"]["max_entries"] == 128
            assert (
                lean_contract["cache"]["warmup_environment_variable"]
                == "JACOBIAN_LEAN_WARMUP=1"
            )

            invoked = await client.call_tool(
                "capability.invoke",
                {
                    "capability_id": "knowledge.search",
                    "mode": "EXPLORE",
                    "payload": {"query": "counterexample", "limit": 5},
                },
            )
            projection = json.loads(invoked.content[0].text)
            assert projection["assurance"]["level"] == "COMPUTED"
            assert projection["output"]["hits"] == []

            unknown = await client.call_tool(
                "capability.invoke",
                {
                    "capability_id": "missing.capability",
                    "mode": "EXPLORE",
                    "payload": {},
                },
            )
            unknown_projection = json.loads(unknown.content[0].text)
            assert unknown.is_error is False
            assert unknown_projection["output"]["error"]["code"] == "UNKNOWN_CAPABILITY"
            assert (
                "capability.describe" in (unknown_projection["output"]["error"]["hint"])
            )

            verified = await client.call_tool("capability.invoke", example)
            verification = json.loads(verified.content[0].text)
            assert verification["execution"]["status"] == "COMPLETED"
            assert verification["assurance"]["level"] == "VERIFIED"

    asyncio.run(scenario())


@pytest.mark.integration
def test_mcp_missing_bundled_services_explain_how_to_recover(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        from mcp import Client

        async with Client(
            create_server(tmp_path, install_references=False),
            raise_exceptions=False,
        ) as client:
            lean = await client.call_tool(
                "lean.verify",
                {
                    "statement": "1 + 1 = 2",
                    "proof": "rfl",
                    "environment": "CORE",
                },
            )
            assert lean.is_error is True
            assert "capability.describe" in lean.content[0].text
            assert "prepare the pinned Lean runtime" in lean.content[0].text
            assert "RuntimeError" not in lean.content[0].text

            workflow = await client.call_tool(
                "verification.run",
                {
                    "reference_name": "graph_paths",
                    "claim_payload": {},
                    "candidate_payload": {},
                    "witness_role": "SUPPORTS_CLAIM",
                },
            )
            assert workflow.is_error is True
            assert "capability.describe" in workflow.content[0].text
            assert "bundled references enabled" in workflow.content[0].text
            assert "RuntimeError" not in workflow.content[0].text

    asyncio.run(scenario())


@pytest.mark.integration
def test_mcp_tool_failures_return_safe_actionable_errors(tmp_path: Path) -> None:
    async def scenario() -> None:
        from mcp import Client

        missing_uri = "artifact://sha256/" + "a" * 64
        async with Client(
            create_server(tmp_path),
            raise_exceptions=False,
        ) as client:
            result = await client.call_tool(
                "artifact.put",
                {
                    "schema_uri": missing_uri,
                    "semantics_uri": missing_uri,
                    "payload": {},
                },
            )
            assert result.is_error is True
            error_text = result.content[0].text
            assert '"code": "INVALID_INPUT"' in error_text
            assert "Check the tool input schema" in error_text
            assert missing_uri not in error_text
            assert "ArtifactNotFoundError" not in error_text

            unknown_reference = await client.call_tool(
                "capability.describe",
                {
                    "capability_id": "reference.solve",
                    "reference_name": "missing-reference",
                },
            )
            response = json.loads(unknown_reference.content[0].text)
            assert response["error"]["code"] == "UNKNOWN_REFERENCE"
            assert "list available references" in response["error"]["hint"]
            assert "missing-reference" not in response["error"]["message"]

    asyncio.run(scenario())


@pytest.mark.integration
def test_mcp_protocol_errors_are_not_converted_to_tool_errors(tmp_path: Path) -> None:
    from mcp.shared.exceptions import MCPError

    server = create_server(tmp_path)

    @server.tool(name="fixture.protocol-error")
    async def protocol_error() -> None:
        raise MCPError(123, "protocol action required")

    with pytest.raises(MCPError, match="protocol action required"):
        asyncio.run(server.call_tool("fixture.protocol-error", {}))


@pytest.mark.integration
def test_mcp_authentication_and_internal_lookup_failures_are_distinct(
    tmp_path: Path,
) -> None:
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
            assert "bearer token" in response.content[0].text
            assert "state-directory permissions" not in response.content[0].text

    asyncio.run(scenario())

    internal = json.loads(_public_tool_error("fixture", KeyError("internal")))
    assert internal["error"]["code"] == "OPERATION_FAILED"


@pytest.mark.integration
def test_mcp_verification_profile_projects_compact_tools_and_domain_contract(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        from mcp import Client

        async with Client(
            create_server(tmp_path, tool_profile=ToolProfile.VERIFICATION),
            raise_exceptions=True,
        ) as client:
            listed = await client.list_tools()
            tools = {tool.name: tool for tool in listed.tools}
            assert set(tools) == VERIFICATION_TOOL_NAMES
            assert all(tool.output_schema is None for tool in tools.values())

            result = await client.read_resource("reference://domain/graph_paths")
            contract = json.loads(result.contents[0].text)
            assert contract["name"] == "graph_paths"
            assert contract["identity"]["domain_id"] == "jacobian.graph-paths"
            assert set(contract["claim_contract"]["predicates"]) == {
                "intended_paths_complete",
                "is_bipartite",
            }
            assert contract["claim_contract"]["base"]["required_capabilities"] == [
                "Evaluator",
                "WitnessOracle",
            ]
            assert contract["candidate_schema"]["properties"]["vertices"]
            assert contract["workflow"]["witness"][0].startswith(
                "call capability.invoke"
            )
            claim_payload = {
                **contract["claim_contract"]["base"],
                "predicate": {"name": "is_bipartite", "parameters": {}},
            }
            response = await client.call_tool(
                "verification.run",
                {
                    "reference_name": "graph_paths",
                    "claim_payload": claim_payload,
                    "candidate_payload": {
                        "vertices": ["a", "b", "c", "d"],
                        "arcs": [
                            ["a", "b"],
                            ["b", "c"],
                            ["c", "d"],
                            ["d", "a"],
                        ],
                    },
                    "witness_role": "SUPPORTS_CLAIM",
                },
            )
            projection = json.loads(response.content[0].text)
            assert projection["evaluation"]["verification"] == "UNVERIFIED"
            assert projection["witness_search"]["verification"] == "UNVERIFIED"
            assert projection["verification"]["verification"] == "VERIFIED"
            assert projection["verification"]["verification_record_uri"].startswith(
                "artifact://sha256/"
            )
            assert "plugin_id" not in projection

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
            args=[
                "-m",
                "jacobian.adapters.mcp.server",
                "--tool-profile",
                "verification",
            ],
            env=environment,
            cwd=Path.cwd(),
        )
        async with Client(
            stdio_client(parameters),
            raise_exceptions=True,
        ) as client:
            listed = await client.list_tools()
            assert {tool.name for tool in listed.tools} == VERIFICATION_TOOL_NAMES

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
