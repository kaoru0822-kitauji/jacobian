"""Executable checks for fixture ownership and state isolation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tests.support.state import copy_template, publish_template

ROOT = Path(__file__).parents[2]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_root_conftest_has_no_high_cost_imports_or_runtime_construction() -> None:
    """Collection of all tiers must not initialize the application runtime."""

    path = ROOT / "conftest.py"
    imports = _imports(path)
    assert not any(
        module.startswith(
            (
                "jacobian.runtime",
                "jacobian.portfolio",
                "jacobian.provider_runtime",
                "jacobian.domains",
                "sympy",
                "networkx",
                "sqlite3",
            )
        )
        for module in imports
    )
    source = path.read_text(encoding="utf-8")
    assert "create_runtime" not in source
    assert "JacobianRuntime" not in source


def test_complete_runtime_fixtures_use_an_explicit_shared_plugin() -> None:
    """Owning tiers register one support module rather than importing conftests."""

    plugin = ROOT / "support" / "runtime_fixtures.py"
    source = plugin.read_text(encoding="utf-8")
    for name in (
        "fresh_complete_runtime",
        "attached_complete_runtime",
        "authorized_complete_runtime",
        "complete_portfolio_template",
    ):
        assert f"def {name}(" in source
    assert "create_runtime" in source

    expected_registration = 'pytest_plugins = ("tests.support.runtime_fixtures",)'
    for tier in ("composition", "boundary", "e2e"):
        tier_source = (ROOT / tier / "conftest.py").read_text(encoding="utf-8")
        assert expected_registration in tier_source
        assert ".conftest import" not in tier_source

    for tier in ("component", "domain"):
        tier_source = (ROOT / tier / "conftest.py").read_text(encoding="utf-8")
        assert "create_runtime" not in tier_source
        assert "BUILTIN_PORTFOLIO" not in tier_source


def test_failed_template_build_has_no_reusable_partial_directory(
    tmp_path: Path,
) -> None:
    """A killed/failed builder cannot leave a target that looks complete."""

    target = tmp_path / "template"

    def fail(staging: Path) -> None:
        (staging / "partial.sqlite3").write_text("incomplete", encoding="utf-8")
        raise RuntimeError("simulated construction failure")

    with pytest.raises(RuntimeError, match="construction failure"):
        publish_template(target, fail)

    assert not target.exists()
    assert not list(tmp_path.glob(".template.staging-*"))
    assert not (tmp_path / "template.ready").exists()


def test_template_isolation_gives_each_test_mutable_state(tmp_path: Path) -> None:
    """Mutating one copied state directory cannot mutate the template."""

    template = tmp_path / "template"
    template.mkdir()
    (template / "metadata.txt").write_text("immutable", encoding="utf-8")
    first = copy_template(template, tmp_path / "first")
    second = copy_template(template, tmp_path / "second")

    (first / "metadata.txt").write_text("first mutation", encoding="utf-8")

    assert (template / "metadata.txt").read_text(encoding="utf-8") == "immutable"
    assert (second / "metadata.txt").read_text(encoding="utf-8") == "immutable"
