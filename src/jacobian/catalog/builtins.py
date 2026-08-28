"""Deterministic discovery of owner-local built-in tool manifests."""

from __future__ import annotations

import pkgutil
from collections import Counter
from importlib import import_module
from typing import Any

import jacobian.math
from jacobian.catalog.models import MathTool, MathTools


def _tool_module_names() -> tuple[str, ...]:
    prefix = f"{jacobian.math.__name__}."
    return tuple(
        sorted(
            module.name
            for module in pkgutil.walk_packages(jacobian.math.__path__, prefix)
            if module.name.endswith("._tools")
        )
    )


def _load_tools(module_names: tuple[str, ...]) -> MathTools:
    tools: list[MathTool[Any, Any]] = []
    for module_name in module_names:
        module = import_module(module_name)
        manifest = getattr(module, "TOOLS", None)
        if not isinstance(manifest, tuple) or not all(
            isinstance(tool, MathTool) for tool in manifest
        ):
            raise TypeError(
                f"{module_name} must export a tuple of MathTool values as TOOLS"
            )
        tools.extend(manifest)

    operation_id_counts = Counter(tool.operation_id for tool in tools)
    duplicates = sorted(
        operation_id for operation_id, count in operation_id_counts.items() if count > 1
    )
    if duplicates:
        raise ValueError(f"built-in operation IDs must be unique: {duplicates}")
    return tuple(sorted(tools, key=lambda tool: tool.operation_id))


_BUILTIN_TOOL_MODULES = _tool_module_names()
BUILTIN_TOOLS: MathTools = _load_tools(_BUILTIN_TOOL_MODULES)

__all__ = ["BUILTIN_TOOLS"]
