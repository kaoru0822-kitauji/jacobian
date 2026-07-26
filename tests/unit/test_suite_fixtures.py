"""Regression coverage for suite-wide fixture snapshots."""

import gc
import shutil
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tests.conftest import _freeze_kernel_store

from jacobian.kernel import JacobianKernel
from jacobian.store import ArtifactStore


def _copy_and_check_store(
    template: Path,
    destination: Path,
    *,
    descriptor_uri: str,
) -> None:
    shutil.copytree(template, destination)
    connection = sqlite3.connect(destination / "metadata.sqlite3")
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    finally:
        connection.close()
    descriptor = ArtifactStore(destination).get_descriptor(
        descriptor_uri,
        expected_kind="schema",
    )
    assert descriptor["name"] == "jacobian.research-episode"


def test_kernel_store_freeze_makes_wal_snapshot_safe_to_copy(tmp_path: Path) -> None:
    template = tmp_path / "template"
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        kernel = JacobianKernel(template)
        descriptor_uri = kernel.memory.episode_schema_uri
        del kernel

        assert (template / "metadata.sqlite3-wal").exists()
        assert (template / "metadata.sqlite3-shm").exists()

        _freeze_kernel_store(template)

        assert not (template / "metadata.sqlite3-wal").exists()
        assert not (template / "metadata.sqlite3-shm").exists()
        connection = sqlite3.connect(template / "metadata.sqlite3")
        try:
            assert connection.execute("PRAGMA journal_mode").fetchone() == ("delete",)
        finally:
            connection.close()

        destinations = [tmp_path / f"clone-{index}" for index in range(8)]
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(
                    _copy_and_check_store,
                    template,
                    destination,
                    descriptor_uri=descriptor_uri,
                )
                for destination in destinations
            ]
            for future in futures:
                future.result()
    finally:
        gc.collect()
        if gc_was_enabled:
            gc.enable()
