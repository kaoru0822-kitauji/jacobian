from __future__ import annotations

import ast
from pathlib import Path

import pytest

_FORBIDDEN_PREFIXES = (
    "jacobian.evaluation",
    "jacobian.plugin_execution",
    "jacobian.plugins",
    "jacobian.shrinking",
    "jacobian.witnesses",
)


@pytest.mark.conformance
def test_independent_checkers_do_not_import_search_implementations() -> None:
    checker_root = Path("src/jacobian_checkers")
    violations: list[str] = []

    for source_path in sorted(checker_root.glob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imported: tuple[str, ...] = ()
            if isinstance(node, ast.Import):
                imported = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported = (node.module,)
            for module in imported:
                if module.startswith(_FORBIDDEN_PREFIXES):
                    violations.append(f"{source_path}:{node.lineno}: {module}")

    assert violations == []
