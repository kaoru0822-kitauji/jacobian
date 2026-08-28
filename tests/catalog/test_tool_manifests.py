"""Fail-closed checks for owner-local public tool manifests."""

from __future__ import annotations

import types

import pytest

from jacobian.catalog.builtins import (
    _BUILTIN_TOOL_MODULES,
    BUILTIN_TOOLS,
    _load_tools,
)


def test_tool_manifest_discovery_is_deterministic_and_owner_local() -> None:
    assert tuple(sorted(_BUILTIN_TOOL_MODULES)) == _BUILTIN_TOOL_MODULES
    assert len(_BUILTIN_TOOL_MODULES) == len(set(_BUILTIN_TOOL_MODULES))
    assert all(
        module_name.startswith("jacobian.math.") and module_name.endswith("._tools")
        for module_name in _BUILTIN_TOOL_MODULES
    )


def test_public_catalog_is_sorted_and_unique() -> None:
    operation_ids = tuple(tool.operation_id for tool in BUILTIN_TOOLS)
    assert operation_ids == tuple(sorted(set(operation_ids)))


def test_tool_loading_rejects_a_malformed_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "jacobian.catalog.builtins.import_module",
        lambda _module_name: types.SimpleNamespace(TOOLS=[]),
    )

    with pytest.raises(TypeError, match="must export a tuple of MathTool values"):
        _load_tools(("jacobian.math.example._tools",))


def test_tool_loading_rejects_duplicate_operation_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = BUILTIN_TOOLS[0]
    monkeypatch.setattr(
        "jacobian.catalog.builtins.import_module",
        lambda _module_name: types.SimpleNamespace(TOOLS=(tool, tool)),
    )

    with pytest.raises(ValueError, match="built-in operation IDs must be unique"):
        _load_tools(("jacobian.math.example._tools",))
