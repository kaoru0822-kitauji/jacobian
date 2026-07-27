"""Suite-wide pytest conventions."""

import gc
import shutil
import sqlite3
from pathlib import Path

import pytest

from tests.sharding import partition_items, validate_shard

_LAYER_MARKERS = {
    "integration": pytest.mark.integration,
    "end_to_end": pytest.mark.end_to_end,
}


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register CI's deterministic collection-partition options."""

    group = parser.getgroup("jacobian")
    group.addoption(
        "--jacobian-shard-count",
        type=int,
        default=1,
        help="Number of stable collection shards.",
    )
    group.addoption(
        "--jacobian-shard-index",
        type=int,
        default=0,
        help="Zero-based stable collection shard to run.",
    )


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

    from jacobian.kernel import JacobianKernel

    template = tmp_path_factory.mktemp("kernel-store-template")
    kernel = JacobianKernel(template)
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


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Keep layer markers aligned with the suite's directory structure."""

    tests_root = Path(__file__).parent
    for item in items:
        try:
            layer = Path(item.path).relative_to(tests_root).parts[0]
        except (ValueError, IndexError):
            continue
        marker = _LAYER_MARKERS.get(layer)
        if marker is not None:
            item.add_marker(marker)

    shard_count = config.getoption("--jacobian-shard-count")
    shard_index = config.getoption("--jacobian-shard-index")
    validate_shard(shard_count, shard_index)
    if shard_count == 1:
        return

    selected, deselected = partition_items(
        items,
        shard_count=shard_count,
        shard_index=shard_index,
    )
    items[:] = selected
    config.hook.pytest_deselected(items=deselected)
