"""Executable contract for the stable MCP tool surface."""

from __future__ import annotations

from jacobian.adapters.mcp.constants import ReasoningLogMode
from jacobian.adapters.mcp.guidance import (
    CAPABILITY_DESCRIBE_DESCRIPTION,
    CAPABILITY_INVOKE_DESCRIPTION,
    SERVER_INSTRUCTIONS,
    render_tool_names,
    tool_names,
)
from jacobian.adapters.mcp.server import JacobianCoreExtension


def test_core_extension_exposes_exactly_the_stable_capability_tools() -> None:
    extension = JacobianCoreExtension(None, None, ReasoningLogMode.OFF)
    assert extension.identifier == "io.jacobian/core"
    assert extension.settings() == {
        "version": "2",
        "reasoning_log_mode": "OFF",
        "tool_name_profile": "capability",
    }
    assert tuple(binding.kwargs["name"] for binding in extension.tools()) == (
        "capability.describe",
        "capability.invoke",
    )


def test_core_extension_can_expose_math_names_without_changing_contracts() -> None:
    extension = JacobianCoreExtension(
        None,
        None,
        ReasoningLogMode.OFF,
        tool_names("math"),
    )

    bindings = extension.tools()
    assert tuple(binding.kwargs["name"] for binding in bindings) == (
        "math.find",
        "math.run",
    )
    assert extension.settings()["tool_name_profile"] == "math"
    assert "capability.describe" not in bindings[1].kwargs["description"]
    assert "math.find" in bindings[1].kwargs["description"]


def test_name_profiles_change_names_without_changing_guidance_semantics() -> None:
    names = tool_names("math")
    assert (
        render_tool_names(SERVER_INSTRUCTIONS, names)
        .replace("math.find", "capability.describe")
        .replace("math.run", "capability.invoke")
        == SERVER_INSTRUCTIONS
    )
    assert (
        render_tool_names(CAPABILITY_DESCRIBE_DESCRIPTION, names)
        .replace("math.find", "capability.describe")
        .replace("math.run", "capability.invoke")
        == CAPABILITY_DESCRIBE_DESCRIPTION
    )
    assert (
        render_tool_names(CAPABILITY_INVOKE_DESCRIPTION, names)
        .replace("math.find", "capability.describe")
        .replace("math.run", "capability.invoke")
        == CAPABILITY_INVOKE_DESCRIPTION
    )


def test_model_visible_guidance_exposes_affordances_without_research_order() -> None:
    combined = "\n".join(
        (
            SERVER_INSTRUCTIONS,
            CAPABILITY_DESCRIBE_DESCRIPTION,
            CAPABILITY_INVOKE_DESCRIPTION,
        )
    ).lower()
    assert "desired local mathematical outcome" in combined
    assert "not recommendations" in combined
    assert "begin with" not in combined
    assert "use this first" not in combined
    assert "call capability.describe first" not in combined
    assert "strongest one or two" not in combined
    assert "before searching for a checker" not in combined
    assert "partition larger searches" not in combined
