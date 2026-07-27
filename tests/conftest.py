"""Suite-wide pytest conventions."""

import gc
import shutil
import sqlite3
from pathlib import Path

import pytest

from jacobian.kernel import JacobianKernel

_LAYER_MARKERS = {
    "integration": pytest.mark.integration,
    "end_to_end": pytest.mark.end_to_end,
}


def _freeze_kernel_store(root: Path) -> None:
    """Checkpoint the template database and remove its volatile WAL files."""

    # sqlite3 connection context managers finish transactions but do not close
    # connections. Kernel construction creates reference cycles containing
    # connections, so make their finalization deterministic before copytree
    # observes WAL/SHM paths that can disappear during a copy.
    gc.collect()

    database = root / "metadata.sqlite3"
    connection = sqlite3.connect(database, timeout=30)
    try:
        checkpoint = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if checkpoint is None or checkpoint[0] != 0:
            raise RuntimeError(
                f"could not checkpoint kernel store template: {checkpoint!r}"
            )
        journal_mode = connection.execute("PRAGMA journal_mode = DELETE").fetchone()
        if journal_mode is None or journal_mode[0].casefold() != "delete":
            raise RuntimeError(
                "could not switch kernel store template to a stable journal mode"
            )
    finally:
        connection.close()

    volatile_paths = (
        database.with_name(f"{database.name}-wal"),
        database.with_name(f"{database.name}-shm"),
    )
    remaining = [path.name for path in volatile_paths if path.exists()]
    if remaining:
        raise RuntimeError(
            f"kernel store template still has volatile SQLite files: {remaining}"
        )


@pytest.fixture(scope="session")
def kernel_store_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build immutable core descriptors once per pytest worker."""

    template = tmp_path_factory.mktemp("kernel-store-template")
    kernel = JacobianKernel(template)
    del kernel
    _freeze_kernel_store(template)
    return template


@pytest.fixture(scope="session")
def kernel_store_template_with_references(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Build an immutable store that already has authorized references installed."""

    template = tmp_path_factory.mktemp("kernel-store-template-with-references")
    kernel = JacobianKernel(template, install_references=True)
    del kernel
    _freeze_kernel_store(template)
    return template


@pytest.fixture
def initialized_kernel_store(
    tmp_path: Path,
    kernel_store_template: Path,
) -> None:
    """Seed an isolated test root with the process's core descriptor snapshot."""

    shutil.copytree(kernel_store_template, tmp_path, dirs_exist_ok=True)


@pytest.fixture
def initialized_kernel_store_with_references(
    tmp_path: Path,
    kernel_store_template_with_references: Path,
) -> None:
    """Seed an isolated test root that already includes authorized references."""

    shutil.copytree(
        kernel_store_template_with_references,
        tmp_path,
        dirs_exist_ok=True,
    )


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Keep layer markers aligned and reject unsafe parallel Lean execution."""

    tests_root = Path(__file__).parent
    for item in items:
        try:
            layer = Path(item.path).relative_to(tests_root).parts[0]
        except (ValueError, IndexError):
            continue
        marker = _LAYER_MARKERS.get(layer)
        if marker is not None:
            item.add_marker(marker)

    workers = config.getoption("numprocesses", default=None)
    if workers in (None, 0, "0"):
        return
    lean_items = [
        item.nodeid for item in items if item.get_closest_marker("lean_runtime")
    ]
    if lean_items:
        sample = ", ".join(lean_items[:3])
        raise pytest.UsageError(
            "Lean runtime tests cannot run under pytest-xdist. "
            "Use `make test` for the non-Lean suite or `make test-lean` "
            f"for serial Lean validation. Selected Lean tests include: {sample}"
        )
