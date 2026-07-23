"""Source identity for installed Python plugin and checker entrypoints."""

from __future__ import annotations

import hashlib
import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


class ImplementationError(RuntimeError):
    """A Python implementation cannot be identified safely."""


class _SourceOnlyLoader(importlib.abc.Loader):
    """Compile one measured module directly from source, bypassing bytecode."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def create_module(self, spec: Any) -> ModuleType | None:
        return None

    def exec_module(self, module: ModuleType) -> None:
        source = self.path.read_bytes()
        code = compile(source, str(self.path), "exec", dont_inherit=True)
        exec(code, module.__dict__)


class _SourceOnlyFinder(importlib.abc.MetaPathFinder):
    """Resolve not-yet-imported modules in one package from measured source."""

    def __init__(self, top_level_package: str) -> None:
        self.top_level_package = top_level_package

    def find_spec(
        self,
        fullname: str,
        path: Any = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        del target
        if fullname != self.top_level_package and not fullname.startswith(
            self.top_level_package + "."
        ):
            return None
        specification = importlib.machinery.PathFinder.find_spec(fullname, path)
        if (
            specification is None
            or specification.origin is None
            or not specification.origin.endswith(".py")
        ):
            return specification
        locations = specification.submodule_search_locations
        return importlib.util.spec_from_file_location(
            fullname,
            specification.origin,
            loader=_SourceOnlyLoader(Path(specification.origin)),
            submodule_search_locations=(
                list(locations) if locations is not None else None
            ),
        )


def install_source_only_importer(entrypoint: str) -> None:
    """Force the entrypoint package's future imports to compile measured source."""

    module_name, _ = split_entrypoint(entrypoint)
    sys.meta_path.insert(0, _SourceOnlyFinder(module_name.split(".", 1)[0]))


def split_entrypoint(entrypoint: str) -> tuple[str, str]:
    try:
        module_name, attribute_name = entrypoint.split(":", 1)
    except ValueError as exc:
        raise ImplementationError(
            "entrypoint must use the form module:attribute"
        ) from exc
    if (
        not module_name
        or not attribute_name
        or any(not part.isidentifier() for part in module_name.split("."))
        or not attribute_name.isidentifier()
    ):
        raise ImplementationError("entrypoint must use the form module:attribute")
    return module_name, attribute_name


def _package_entries(module_name: str) -> list[tuple[str, Path]]:
    """Resolve a module from its top-level package without importing parents."""

    top_level, *remaining = module_name.split(".")
    specification = importlib.machinery.PathFinder.find_spec(top_level)
    if specification is None:
        raise ImplementationError(f"cannot resolve package {top_level!r}")

    locations = specification.submodule_search_locations
    if locations:
        roots = [Path(location) for location in locations]
        if not _module_exists_in_roots(roots, remaining):
            raise ImplementationError(f"cannot resolve module {module_name!r}")
        entries: list[tuple[str, Path]] = []
        for root_index, root in enumerate(roots):
            if root.is_symlink() or not root.is_dir():
                raise ImplementationError(
                    f"package root is not a regular directory: {root}"
                )
            for directory, names, files in os.walk(root, followlinks=False):
                directory_path = Path(directory)
                for name in names:
                    child = directory_path / name
                    if child.is_symlink():
                        raise ImplementationError(
                            f"package source contains a symlink: {child}"
                        )
                for name in files:
                    if not name.endswith(".py"):
                        continue
                    source = directory_path / name
                    if source.is_symlink() or not source.is_file():
                        raise ImplementationError(
                            f"package source is not a regular file: {source}"
                        )
                    relative = source.relative_to(root).as_posix()
                    entries.append((f"{root_index}:{top_level}/{relative}", source))
        if not entries:
            raise ImplementationError(f"package {top_level!r} has no Python source")
        return sorted(entries)

    if specification.origin is None:
        raise ImplementationError(f"module {top_level!r} has no source")
    source = Path(specification.origin)
    if remaining:
        raise ImplementationError(f"{top_level!r} is not a package")
    if source.is_symlink() or not source.is_file() or source.suffix != ".py":
        raise ImplementationError(
            f"module source is not a regular Python file: {source}"
        )
    return [(f"{top_level}.py", source)]


def _module_exists_in_roots(roots: list[Path], remaining: list[str]) -> bool:
    for root in roots:
        if not remaining:
            if (root / "__init__.py").is_file():
                return True
            continue
        relative = Path(*remaining)
        module_file = root / relative.with_suffix(".py")
        package_file = root / relative / "__init__.py"
        for candidate in (module_file, package_file):
            if candidate.is_file() and not candidate.is_symlink():
                return True
    return False


def package_source_digest(entrypoint: str) -> str:
    """Hash all Python source in an entrypoint's top-level package.

    Binding the package rather than only the named module prevents unchecked
    helper-module edits from changing an authorized implementation.
    """

    module_name, _ = split_entrypoint(entrypoint)
    digest = hashlib.sha256()
    digest.update(b"jacobian.python-package.v1\x00")
    digest.update(module_name.split(".", 1)[0].encode("utf-8"))
    digest.update(b"\x00")
    for relative_name, source in _package_entries(module_name):
        name_bytes = relative_name.encode("utf-8")
        content = source.read_bytes()
        digest.update(len(name_bytes).to_bytes(8, "big"))
        digest.update(name_bytes)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()


def module_source_digest(entrypoint: str) -> str:
    """Compatibility alias for the v0.2 implementation descriptor."""

    return package_source_digest(entrypoint)
