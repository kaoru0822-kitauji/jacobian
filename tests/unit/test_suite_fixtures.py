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


def _research_episode_schema_uri(root: Path) -> str:
    connection = sqlite3.connect(root / "metadata.sqlite3")
    try:
        row = connection.execute(
            "SELECT artifact_uri FROM artifacts WHERE summary = ?",
            ("schema: jacobian.research-episode@1",),
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    return str(row[0])


def test_kernel_store_freeze_removes_deferred_wal_files(tmp_path: Path) -> None:
    template = tmp_path / "template"
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        kernel = JacobianKernel(template)
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
    finally:
        gc.collect()
        if gc_was_enabled:
            gc.enable()


def test_kernel_store_template_is_quiescent_and_copyable(
    kernel_store_template: Path,
    tmp_path: Path,
) -> None:
    database = kernel_store_template / "metadata.sqlite3"
    assert not database.with_name(f"{database.name}-wal").exists()
    assert not database.with_name(f"{database.name}-shm").exists()

    connection = sqlite3.connect(database)
    try:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("delete",)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    finally:
        connection.close()

    descriptor_uri = _research_episode_schema_uri(kernel_store_template)
    destinations = [tmp_path / f"clone-{index}" for index in range(8)]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(
                _copy_and_check_store,
                kernel_store_template,
                destination,
                descriptor_uri=descriptor_uri,
            )
            for destination in destinations
        ]
        for future in futures:
            future.result()
    gc.collect()


def test_kernel_store_template_with_references_is_quiescent_and_copyable(
    kernel_store_template_with_references: Path,
    tmp_path: Path,
) -> None:
    database = kernel_store_template_with_references / "metadata.sqlite3"
    assert not database.with_name(f"{database.name}-wal").exists()
    assert not database.with_name(f"{database.name}-shm").exists()

    connection = sqlite3.connect(database)
    try:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("delete",)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    finally:
        connection.close()

    descriptor_uri = _research_episode_schema_uri(kernel_store_template_with_references)
    destination = tmp_path / "clone-with-references"
    _copy_and_check_store(
        kernel_store_template_with_references,
        destination,
        descriptor_uri=descriptor_uri,
    )
    kernel = JacobianKernel(destination, install_references=True)
    assert "graph_paths" in kernel.references
    assert "erdos_straus" in kernel.references
