from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

_ROOT = Path(__file__).parents[3]


def _collect_string_entrypoints(text: str, by_module: dict[str, set[str]]) -> None:
    """Collect jacobian_checkers.module:function patterns from source text."""

    for m in re.finditer(r"jacobian_checkers\.(\w+):(\w+)", text):
        by_module.setdefault(m.group(1), set()).add(m.group(2))
    for m in re.finditer(r'jacobian_checkers\.(\w+):\s*"\s*\n\s*"(\w+)"', text):
        by_module.setdefault(m.group(1), set()).add(m.group(2))


def _build_var_map(tree: ast.Module) -> dict[str, str]:
    """Map top-level variable names to their constant string values."""

    var_map: dict[str, str] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(
                    node.value, ast.Constant
                ):
                    value = node.value.value
                    if isinstance(value, str):
                        var_map[target.id] = value
    return var_map


def _resolve_entrypoint_module(
    kw: ast.keyword, var_map: dict[str, str]
) -> str:
    """Resolve an entrypoint_module keyword to its module string."""

    if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
        return kw.value.value
    if isinstance(kw.value, ast.Name) and kw.value.id in var_map:
        return var_map[kw.value.id]
    return "jacobian_checkers.exact_domain_operations"


def _collect_declaration_entrypoints(
    text: str, by_module: dict[str, set[str]]
) -> None:
    """Collect ExactReplayCheckerDeclaration function + entrypoint_module pairs."""

    if "ExactReplayCheckerDeclaration" not in text:
        return
    tree = ast.parse(text)
    var_map = _build_var_map(tree)
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "ExactReplayCheckerDeclaration"
        ):
            continue
        func: str | None = None
        mod = "exact_domain_operations"
        if (
            len(node.args) >= 3
            and isinstance(node.args[2], ast.Constant)
            and isinstance(node.args[2].value, str)
        ):
            func = node.args[2].value
        for kw in node.keywords:
            if (
                kw.arg == "function"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                func = kw.value.value
            elif kw.arg == "entrypoint_module":
                mod = _resolve_entrypoint_module(kw, var_map)
        if func is not None:
            by_module.setdefault(mod.replace("jacobian_checkers.", ""), set()).add(
                func
            )


def _collect_registered_entrypoints() -> dict[str, set[str]]:
    """Return {checker_module_short_name: {function_name, ...}}."""

    by_module: dict[str, set[str]] = {}
    src = _ROOT / "src" / "jacobian"
    for py in sorted(src.rglob("*.py")):
        text = py.read_text(encoding="utf-8")
        _collect_string_entrypoints(text, by_module)
        _collect_declaration_entrypoints(text, by_module)
    return by_module


_REGISTERED = _collect_registered_entrypoints()


def test_registered_checker_entrypoints_are_exported() -> None:
    """Every checker function referenced as a registered entrypoint in
    ``src/jacobian`` must appear in its module's ``__all__`` manifest."""

    violations: list[str] = []
    for mod_short, funcs in sorted(_REGISTERED.items()):
        module = importlib.import_module(f"jacobian_checkers.{mod_short}")
        exported = set(getattr(module, "__all__", ()))
        for func in sorted(funcs):
            if func not in exported:
                violations.append(
                    f"jacobian_checkers.{mod_short}:{func} is registered as an "
                    f"entrypoint but missing from __all__"
                )
    assert not violations, "\n".join(violations)
