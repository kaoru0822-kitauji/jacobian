from __future__ import annotations

import asyncio

import pytest

from jacobian.adapters.mcp import readiness


def test_readiness_matches_current_sdk2_tool_surface() -> None:
    assert {
        "capability.describe",
        "capability.invoke",
    } == readiness.EXPECTED_TOOLS


def test_readiness_retries_transient_startup_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    async def inspect(_url: str, *, required_capability: str) -> dict[str, object]:
        nonlocal attempts
        attempts += 1
        assert required_capability == "graph.search.atlas"
        if attempts == 1:
            raise ConnectionError("starting")
        return {"required_capability": required_capability}

    async def no_wait(_delay: float) -> None:
        return None

    monkeypatch.setattr(readiness, "inspect_once", inspect)
    monkeypatch.setattr(readiness.asyncio, "sleep", no_wait)

    report = asyncio.run(
        readiness.wait_until_ready(
            "http://jacobian:8000/mcp",
            required_capability="graph.search.atlas",
            timeout_seconds=2.0,
        )
    )

    assert attempts == 2
    assert report["required_capability"] == "graph.search.atlas"


def test_readiness_bounds_a_hung_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def inspect(_url: str, *, required_capability: str) -> dict[str, object]:
        del required_capability
        await asyncio.sleep(60)
        return {}

    monkeypatch.setattr(readiness, "inspect_once", inspect)

    with pytest.raises(RuntimeError, match="did not become ready"):
        asyncio.run(
            readiness.wait_until_ready(
                "http://jacobian:8000/mcp",
                required_capability="graph.search.atlas",
                timeout_seconds=0.01,
            )
        )
