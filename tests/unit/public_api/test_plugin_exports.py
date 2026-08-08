from __future__ import annotations

import importlib

import pytest

PLUGIN_EXPORTS = {
    "jacobian.plugins": (),
    "jacobian.plugins.erdos_straus": (
        "evaluate_capability",
        "find_witness_capability",
    ),
    "jacobian.plugins.graph_paths": (
        "canonicalize_capability",
        "enumerate_candidates_capability",
        "evaluate_capability",
        "find_witness_capability",
        "materialize",
        "reductions_capability",
    ),
    "jacobian.plugins.graph_shrinking": ("reduce_simple_graph",),
    "jacobian.plugins.matrices": (
        "enumerate_candidates_capability",
        "evaluate_capability",
        "find_witness_capability",
        "materialize",
        "reductions_capability",
        "transform_row_major_capability",
    ),
    "jacobian.plugins.registry": (
        "PluginRegistry",
        "PluginRegistryError",
        "ResolvedCapability",
    ),
}


@pytest.mark.parametrize("module_name", PLUGIN_EXPORTS)
def test_plugin_modules_declare_their_supported_symbols(module_name: str) -> None:
    module = importlib.import_module(module_name)
    names = PLUGIN_EXPORTS[module_name]

    assert tuple(module.__all__) == names
    assert all(hasattr(module, name) for name in names)
