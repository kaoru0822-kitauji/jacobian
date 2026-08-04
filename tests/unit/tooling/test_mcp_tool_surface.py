"""Executable contract for the stable MCP tool surface."""

from __future__ import annotations

from jacobian.adapters.mcp.constants import ReasoningLogMode
from jacobian.adapters.mcp.server import JacobianCoreExtension


def test_core_extension_exposes_exactly_the_stable_capability_tools() -> None:
    extension = JacobianCoreExtension(None, None, ReasoningLogMode.OFF)
    assert extension.identifier == "io.jacobian/core"
    assert extension.settings() == {"version": "2", "reasoning_log_mode": "OFF"}
    assert tuple(binding.kwargs["name"] for binding in extension.tools()) == (
        "capability.describe",
        "capability.invoke",
    )
