from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from mcp import Client

from jacobian.adapters.mcp.server import create_server

pytestmark = [
    pytest.mark.usefixtures("initialized_kernel_store_with_references"),
]


def _q(value: int) -> dict[str, str]:
    return {"num": str(value), "den": "1"}


def _polynomial(*coefficients_ascending: int) -> dict[str, object]:
    return {
        "variables": ["x"],
        "polynomial": {
            "terms": [
                {
                    "coefficient": _q(coefficient),
                    "exponents": [exponent],
                }
                for exponent, coefficient in reversed(
                    tuple(enumerate(coefficients_ascending))
                )
                if coefficient
            ]
        },
    }


async def _tool(client: Client, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    result = await client.call_tool(name, arguments)
    assert result.is_error is False
    return json.loads(result.content[0].text)


async def _catalog(client: Client) -> set[str]:
    result = await client.read_resource("capability://catalog")
    catalog = json.loads(result.contents[0].text)
    return {descriptor["capability_id"] for descriptor in catalog["capabilities"]}


async def _artifact(client: Client, artifact_uri: str) -> dict[str, Any]:
    result = await client.read_resource(artifact_uri)
    return json.loads(result.contents[0].text)


def test_exact_domain_result_verifies_and_replays_after_restart(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        server = create_server(tmp_path, install_references=True)
        async with Client(server, raise_exceptions=True) as client:
            capability_ids = await _catalog(client)
            assert {
                "polynomial.compute.gcd",
                "polynomial.result.verify",
            } <= capability_ids

            producer = await _tool(
                client,
                "capability.describe",
                {"capability_id": "polynomial.compute.gcd"},
            )
            verifier = await _tool(
                client,
                "capability.describe",
                {"capability_id": "polynomial.result.verify"},
            )
            assert producer["capability"]["modes"] == ["EXPLORE"]
            assert verifier["capability"]["modes"] == ["VERIFY"]

            computed = await _tool(
                client,
                "capability.invoke",
                {
                    "capability_id": "polynomial.compute.gcd",
                    "mode": "EXPLORE",
                    "payload": {
                        "left": _polynomial(-1, 0, 1),
                        "right": _polynomial(0, 1, 1),
                    },
                },
            )
            assert computed["execution"]["status"] == "COMPLETED"
            assert computed["assurance"]["level"] == "COMPUTED"
            result_uri = computed["output"]["result_uri"]

            verified = await _tool(
                client,
                "capability.invoke",
                {
                    "capability_id": "polynomial.result.verify",
                    "mode": "VERIFY",
                    "payload": {"result_uri": result_uri},
                },
            )
            assert verified["output"]["status"] == "VERIFIED"
            assert verified["assurance"]["level"] == "VERIFIED"
            record_uri = verified["output"]["verification_record_uri"]
            assert record_uri in verified["artifact_uris"]
            record = await _artifact(client, record_uri)
            assert record["artifact_uri"] == record_uri
            assert record["payload"]["evidence_uri"] in verified["artifact_uris"]

        restarted = create_server(tmp_path, install_references=True)
        async with Client(restarted, raise_exceptions=True) as client:
            replayed = await _tool(
                client,
                "capability.invoke",
                {
                    "capability_id": "polynomial.result.verify",
                    "mode": "VERIFY",
                    "payload": {"result_uri": result_uri},
                },
            )
            assert replayed["output"]["status"] == "VERIFIED"
            assert replayed["output"]["verification_record_uri"] == record_uri
            assert (await _artifact(client, record_uri))["artifact_uri"] == record_uri

    asyncio.run(scenario())


def test_computed_domain_operation_remains_available_without_checker_authority(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        server = create_server(tmp_path, install_references=False)
        async with Client(server, raise_exceptions=True) as client:
            capability_ids = await _catalog(client)
            assert "polynomial.compute.gcd" in capability_ids
            assert "polynomial.result.verify" not in capability_ids

            computed = await _tool(
                client,
                "capability.invoke",
                {
                    "capability_id": "polynomial.compute.gcd",
                    "mode": "EXPLORE",
                    "payload": {
                        "left": _polynomial(-1, 0, 1),
                        "right": _polynomial(0, 1, 1),
                    },
                },
            )
            assert computed["execution"]["status"] == "COMPLETED"
            assert computed["assurance"]["level"] == "COMPUTED"
            assert computed["assurance"]["verification_record_uri"] is None

            unavailable = await _tool(
                client,
                "capability.invoke",
                {
                    "capability_id": "polynomial.result.verify",
                    "mode": "VERIFY",
                    "payload": {"result_uri": computed["output"]["result_uri"]},
                },
            )
            assert unavailable["execution"]["status"] == "ERROR"
            assert unavailable["output"]["error"]["code"] == "UNKNOWN_CAPABILITY"
            assert unavailable["assurance"]["level"] == "HEURISTIC"

    asyncio.run(scenario())


@pytest.mark.external_backend
@pytest.mark.lean_runtime
@pytest.mark.skipif(shutil.which("lean") is None, reason="Lean is not installed")
def test_lean_proof_edit_verifies_through_mcp_and_replays_after_restart(
    tmp_path: Path,
) -> None:
    async def validate(client: Client) -> dict[str, Any]:
        capability_ids = await _catalog(client)
        assert "lean.proof_edit.validate" in capability_ids
        descriptor = await _tool(
            client,
            "capability.describe",
            {"capability_id": "lean.proof_edit.validate"},
        )
        assert descriptor["capability"]["modes"] == ["VERIFY"]
        return await _tool(
            client,
            "capability.invoke",
            {
                "capability_id": "lean.proof_edit.validate",
                "mode": "VERIFY",
                "payload": {
                    "environment": "CORE",
                    "statement": "True",
                    "original_proof": "by\n  exact True.intro",
                    "edited_proof": "by\n  trivial",
                },
            },
        )

    async def scenario() -> None:
        server = create_server(tmp_path, install_references=True)
        async with Client(server, raise_exceptions=True) as client:
            verified = await validate(client)
            assert verified["output"]["accepted"] is True
            assert verified["assurance"]["level"] == "VERIFIED"
            assert verified["completeness"]["status"] == "NOT_APPLICABLE"
            record_uri = verified["output"]["verification_record_uri"]
            assert record_uri in verified["artifact_uris"]
            assert verified["output"]["proof_edit_uri"] in verified["artifact_uris"]
            record = await _artifact(client, record_uri)
            assert record["artifact_uri"] == record_uri
            assert record["payload"]["evidence_uri"] in verified["artifact_uris"]

        restarted = create_server(tmp_path, install_references=True)
        async with Client(restarted, raise_exceptions=True) as client:
            replayed = await validate(client)
            assert replayed["output"]["accepted"] is True
            assert replayed["output"]["verification_record_uri"] == record_uri
            assert (await _artifact(client, record_uri))["artifact_uri"] == record_uri

    asyncio.run(scenario())
