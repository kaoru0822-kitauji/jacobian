from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from jacobian.adapters.mcp.remote import (
    StaticTokenGrant,
    StaticTokenVerifier,
    TenantKernelRouter,
    load_static_token_file,
)
from jacobian.store import ArtifactNotFoundError


@pytest.mark.integration
def test_static_tokens_bind_distinct_authenticated_subjects() -> None:
    verifier = StaticTokenVerifier(
        (
            StaticTokenGrant(tenant_id="alpha", token="a" * 32),
            StaticTokenGrant(tenant_id="beta", token="b" * 32),
        )
    )

    alpha = asyncio.run(verifier.verify_token("a" * 32))
    beta = asyncio.run(verifier.verify_token("b" * 32))
    unknown = asyncio.run(verifier.verify_token("c" * 32))

    assert alpha is not None and alpha.subject == "alpha"
    assert beta is not None and beta.subject == "beta"
    assert unknown is None


@pytest.mark.integration
def test_tenant_router_isolates_artifact_stores(tmp_path: Path) -> None:
    router = TenantKernelRouter(tmp_path, install_references=False)
    alpha = router.kernel_for("alpha")
    beta = router.kernel_for("beta")
    stored = alpha.store.register_descriptor(
        kind="semantics",
        name="alpha-only",
        version="1",
        definition={"value": 1},
    )

    assert alpha.store.root != beta.store.root
    with pytest.raises(ArtifactNotFoundError):
        beta.store.get(stored)


@pytest.mark.integration
def test_token_file_is_strict_and_remote_cli_fails_closed(
    tmp_path: Path,
) -> None:
    token_file = tmp_path / "tokens.json"
    token_file.write_text(
        json.dumps(
            {
                "tokens": [
                    {
                        "tenant_id": "alpha",
                        "token": "a" * 32,
                        "scopes": ["jacobian:use"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert load_static_token_file(token_file)[0].tenant_id == "alpha"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "jacobian.adapters.mcp.server",
            "--transport",
            "streamable-http",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode != 0
    assert "require --auth-tokens-file" in completed.stderr


@pytest.mark.integration
@pytest.mark.subprocess
def test_authenticated_streamable_http_isolates_tenant_memory(
    tmp_path: Path,
) -> None:
    token_file = tmp_path / "tokens.json"
    token_file.write_text(
        json.dumps(
            {
                "tokens": [
                    {"tenant_id": "alpha", "token": "a" * 32},
                    {"tenant_id": "beta", "token": "b" * 32},
                ]
            }
        ),
        encoding="utf-8",
    )
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = int(reserved.getsockname()[1])
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "jacobian.adapters.mcp.server",
            "--transport",
            "streamable-http",
            "--tool-profile",
            "capabilities",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--state-dir",
            str(tmp_path / "state"),
            "--auth-tokens-file",
            str(token_file),
            "--public-base-url",
            f"http://127.0.0.1:{port}",
            "--capability-adapter",
            "tests.fixtures.capability_functions:create_adapter",
        ],
        cwd=Path.cwd(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_port(port, process)
        asyncio.run(_remote_tenant_scenario(port))
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


async def _remote_tenant_scenario(port: int) -> None:
    import httpx2
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    url = f"http://127.0.0.1:{port}/mcp"

    async def invoke(token: str, *, create: bool) -> int:
        async with (
            httpx2.AsyncClient(
                headers={"Authorization": f"Bearer {token}"},
                trust_env=False,
            ) as http,
            Client(
                streamable_http_client(url, http_client=http),
                raise_exceptions=True,
            ) as client,
        ):
            catalog = await client.read_resource("capability://catalog")
            assert "fixture.increment" in catalog.contents[0].text
            if create:
                await client.call_tool(
                    "capability.invoke",
                    {
                        "capability_id": "fixture.increment",
                        "mode": "EXPLORE",
                        "payload": {"value": 4},
                    },
                )
            searched = await client.call_tool(
                "capability.invoke",
                {
                    "capability_id": "knowledge.search",
                    "mode": "EXPLORE",
                    "payload": {"query": "fixture.increment"},
                },
            )
            payload = json.loads(searched.content[0].text)
            assert payload["execution"]["status"] == "COMPLETED", payload["execution"]
            assert "hits" in payload["output"], payload
            return len(payload["output"]["hits"])

    assert await invoke("a" * 32, create=True) == 1
    assert await invoke("b" * 32, create=False) == 0


def _wait_for_port(port: int, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr is not None else ""
            raise AssertionError(f"remote MCP server exited early: {stderr}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise AssertionError("remote MCP server did not start")
