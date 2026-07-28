from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEST_ROOTS = {
    "unit",
    "contract",
    "checkers",
    "reference",
    "integration",
    "end_to_end",
}
LAYER_MARKERS = {"contract", "integration", "end_to_end"}


def test_every_test_module_has_semantic_directory_ownership() -> None:
    unowned = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "tests").rglob("test_*.py")
        if path.relative_to(ROOT / "tests").parts[0] not in TEST_ROOTS
    ]

    assert unowned == []


def test_layer_ownership_is_not_duplicated_in_markers() -> None:
    violations: list[str] = []
    for path in (ROOT / "tests").rglob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            if (
                isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "pytest"
                and node.value.attr == "mark"
                and node.attr in LAYER_MARKERS
            ):
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")

    assert violations == []
