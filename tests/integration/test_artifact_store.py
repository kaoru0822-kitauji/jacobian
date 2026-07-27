from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from jacobian.canonical import CanonicalizationError
from jacobian.store import (
    ArtifactIntegrityError,
    ArtifactStore,
    StoreError,
    StoreLimitError,
    StoreLimits,
)


@pytest.mark.integration
@pytest.mark.conformance
def test_artifact_identity_uses_canonical_payload_schema_and_semantics(
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path)
    schema_a = store.register_descriptor(
        kind="schema",
        name="example.candidate",
        version="1",
        definition={"type": "object"},
    )
    schema_b = store.register_descriptor(
        kind="schema",
        name="example.candidate.alternate",
        version="1",
        definition={"type": "object"},
    )
    semantics_a = store.register_descriptor(
        kind="semantics",
        name="example.meaning",
        version="1",
        definition={"description": "first meaning"},
    )
    semantics_b = store.register_descriptor(
        kind="semantics",
        name="example.meaning.alternate",
        version="1",
        definition={"description": "second meaning"},
    )

    first = store.put(
        schema_uri=schema_a,
        semantics_uri=semantics_a,
        payload={"weight": {"num": "2", "den": "4"}},
        summary="candidate",
    )
    equivalent = store.put(
        schema_uri=schema_a,
        semantics_uri=semantics_a,
        payload={"weight": {"num": "1", "den": "2"}},
        summary="candidate",
    )
    different_schema = store.put(
        schema_uri=schema_b,
        semantics_uri=semantics_a,
        payload={"weight": {"num": "1", "den": "2"}},
        summary="candidate",
    )
    different_semantics = store.put(
        schema_uri=schema_a,
        semantics_uri=semantics_b,
        payload={"weight": {"num": "1", "den": "2"}},
        summary="candidate",
    )

    assert first == equivalent
    assert (
        len(
            {
                first.object_digest,
                different_schema.object_digest,
                different_semantics.object_digest,
            }
        )
        == 3
    )
    assert store.get(first.artifact_uri).payload == {"weight": {"den": "2", "num": "1"}}


@pytest.mark.integration
@pytest.mark.conformance
def test_modified_blob_is_rejected_on_read(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    schema = store.register_descriptor(
        kind="schema",
        name="example.candidate",
        version="1",
        definition={"type": "object"},
    )
    semantics = store.register_descriptor(
        kind="semantics",
        name="example.meaning",
        version="1",
        definition={"description": "meaning"},
    )
    artifact = store.put(
        schema_uri=schema,
        semantics_uri=semantics,
        payload={"value": "original"},
    )

    payload_blob = next(
        path
        for path in (tmp_path / "blobs" / "sha256").glob("*/*")
        if path.read_bytes() == b'{"value":"original"}'
    )
    payload_blob.write_bytes(b'{"value":"tampered"}')

    with pytest.raises(ArtifactIntegrityError):
        store.get(artifact.artifact_uri)


@pytest.mark.integration
@pytest.mark.conformance
@pytest.mark.parametrize("column", ["manifest_digest", "summary"])
def test_modified_artifact_metadata_is_rejected_on_read(
    tmp_path: Path,
    column: str,
) -> None:
    store = ArtifactStore(tmp_path)
    schema = store.register_descriptor(
        kind="schema",
        name="example.candidate",
        version="1",
        definition={"type": "object"},
    )
    semantics = store.register_descriptor(
        kind="semantics",
        name="example.meaning",
        version="1",
        definition={"description": "meaning"},
    )
    artifact = store.put(
        schema_uri=schema,
        semantics_uri=semantics,
        payload={"value": "original"},
        summary="original summary",
    )

    replacement = (
        "sha256:" + "0" * 64 if column == "manifest_digest" else "tampered summary"
    )
    with sqlite3.connect(store.db_path) as connection:
        if column == "manifest_digest":
            connection.execute(
                """
                UPDATE artifacts
                SET manifest_digest = ?
                WHERE artifact_uri = ?
                """,
                (replacement, artifact.artifact_uri),
            )
        else:
            connection.execute(
                """
                UPDATE artifacts
                SET summary = ?
                WHERE artifact_uri = ?
                """,
                (replacement, artifact.artifact_uri),
            )

    with pytest.raises(ArtifactIntegrityError, match="manifest differs"):
        store.get(artifact.artifact_uri)


@pytest.mark.integration
@pytest.mark.conformance
@pytest.mark.parametrize("missing_reference", ["parent", "schema", "semantics"])
def test_missing_reference_metadata_is_rejected_on_read(
    tmp_path: Path,
    missing_reference: str,
) -> None:
    store = ArtifactStore(tmp_path)
    schema = store.register_descriptor(
        kind="schema",
        name="example.candidate",
        version="1",
        definition={"type": "object"},
    )
    semantics = store.register_descriptor(
        kind="semantics",
        name="example.meaning",
        version="1",
        definition={"description": "meaning"},
    )
    parent = store.put(
        schema_uri=schema,
        semantics_uri=semantics,
        payload={"kind": "parent"},
    )
    child = store.put(
        schema_uri=schema,
        semantics_uri=semantics,
        payload={"kind": "child"},
        parents=(parent.artifact_uri,),
    )

    deleted_uri = {
        "parent": parent.artifact_uri,
        "schema": schema,
        "semantics": semantics,
    }[missing_reference]
    with sqlite3.connect(store.db_path) as connection:
        connection.execute(
            "DELETE FROM artifacts WHERE artifact_uri = ?",
            (deleted_uri,),
        )

    with pytest.raises(ArtifactIntegrityError, match="is not committed"):
        store.get(child.artifact_uri)


@pytest.mark.integration
@pytest.mark.conformance
def test_over_limit_artifact_leaves_no_partial_metadata(tmp_path: Path) -> None:
    store = ArtifactStore(
        tmp_path,
        limits=StoreLimits(
            max_artifact_bytes=2048,
            max_total_blob_bytes=1024 * 1024,
        ),
    )
    schema = store.register_descriptor(
        kind="schema",
        name="bounded.candidate",
        version="1",
        definition={"type": "object"},
    )
    semantics = store.register_descriptor(
        kind="semantics",
        name="bounded.candidate",
        version="1",
        definition={"description": "bounded fixture"},
    )
    blobs_before = {
        path.relative_to(tmp_path)
        for path in (tmp_path / "blobs" / "sha256").glob("*/*")
    }

    with pytest.raises(CanonicalizationError, match="size limit"):
        store.put(
            schema_uri=schema,
            semantics_uri=semantics,
            payload={"value": "x" * 4096},
        )

    blobs_after = {
        path.relative_to(tmp_path)
        for path in (tmp_path / "blobs" / "sha256").glob("*/*")
    }
    assert blobs_after == blobs_before


@pytest.mark.integration
@pytest.mark.conformance
def test_concurrent_blob_commits_cannot_oversubscribe_quota(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ArtifactStore(
        tmp_path,
        limits=StoreLimits(
            max_artifact_bytes=2048,
            max_total_blob_bytes=900,
        ),
    )
    first_accounting = threading.Event()
    release_first = threading.Event()
    call_lock = threading.Lock()
    accounting_calls = 0
    original_accounting = store._blob_bytes_committed

    def paused_accounting() -> int:
        nonlocal accounting_calls
        with call_lock:
            accounting_calls += 1
            call_number = accounting_calls
        if call_number == 1:
            first_accounting.set()
            assert release_first.wait(timeout=2)
        return original_accounting()

    monkeypatch.setattr(store, "_blob_bytes_committed", paused_accounting)
    outcomes: list[Any] = []

    def commit(data: bytes) -> None:
        try:
            outcomes.append(store._write_blob(data))
        except Exception as exc:
            outcomes.append(exc)

    first = threading.Thread(target=commit, args=(b"a" * 600,))
    second = threading.Thread(target=commit, args=(b"b" * 600,))
    first.start()
    assert first_accounting.wait(timeout=1)
    second.start()
    time.sleep(0.1)

    with call_lock:
        assert accounting_calls == 1

    release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert sum(isinstance(outcome, str) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, StoreLimitError) for outcome in outcomes) == 1


@pytest.mark.integration
def test_blob_writes_do_not_rescan_the_blob_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ArtifactStore(tmp_path)

    def unexpected_scan(_path: Path) -> None:
        raise AssertionError("blob writes must use durable quota accounting")

    monkeypatch.setattr(Path, "iterdir", unexpected_scan)
    store._write_blob(b"constant-time quota accounting")


@pytest.mark.integration
def test_store_open_reconciles_stale_quota_metadata(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    committed = store._blob_bytes_committed()
    store._adjust_blob_bytes_committed(512)

    reopened = ArtifactStore(tmp_path)

    assert reopened._blob_bytes_committed() == committed


@pytest.mark.integration
def test_duplicate_put_uses_store_open_integrity_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ArtifactStore(tmp_path)
    data = b"validated once per unchanged blob"
    digest = store._write_blob(data)

    def unexpected_read(_path: Path) -> bytes:
        raise AssertionError("unchanged validated blobs must not be reread")

    monkeypatch.setattr(Path, "read_bytes", unexpected_read)

    assert store._write_blob(data) == digest


@pytest.mark.integration
def test_duplicate_put_rechecks_a_changed_blob(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    original = b"original"
    digest = store._write_blob(original)
    store._blob_path(digest).write_bytes(b"tampered")

    with pytest.raises(ArtifactIntegrityError, match="does not match"):
        store._write_blob(original)


@pytest.mark.integration
def test_failed_blob_publication_releases_quota_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ArtifactStore(tmp_path)
    committed = store._blob_bytes_committed()

    def fail_link(_source: str, _target: str) -> None:
        raise OSError("link failed")

    monkeypatch.setattr(os, "link", fail_link)

    with pytest.raises(StoreError, match="could not write"):
        store._write_blob(b"unpublished")

    assert store._blob_bytes_committed() == committed


@pytest.mark.integration
def test_cross_process_blob_writes_cannot_oversubscribe_quota(
    tmp_path: Path,
) -> None:
    script = """
import sys
from jacobian.store import ArtifactStore, StoreLimitError, StoreLimits

store = ArtifactStore(sys.argv[1], limits=StoreLimits(max_total_blob_bytes=900))
try:
    store._write_blob(sys.argv[2].encode("ascii") * 600)
except StoreLimitError:
    print("limited")
else:
    print("committed")
"""
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(tmp_path), value],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for value in ("a", "b")
    ]
    completed = [process.communicate(timeout=30) for process in processes]

    assert [process.returncode for process in processes] == [0, 0]
    assert sorted(stdout.strip() for stdout, _stderr in completed) == [
        "committed",
        "limited",
    ]


@pytest.mark.integration
@pytest.mark.conformance
def test_store_keeps_filesystem_paths_local(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = ArtifactStore(tmp_path)
    schema = store.register_descriptor(
        kind="schema",
        name="example.candidate",
        version="1",
        definition={"type": "object"},
    )
    semantics = store.register_descriptor(
        kind="semantics",
        name="example.meaning",
        version="1",
        definition={"description": "meaning"},
    )
    original_mkdir = Path.mkdir

    def fail_blob_directory(
        path: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        if store.blob_root in path.parents:
            raise OSError("simulated filesystem failure at /private/provider/blob/path")
        original_mkdir(
            path,
            mode=mode,
            parents=parents,
            exist_ok=exist_ok,
        )

    monkeypatch.setattr(Path, "mkdir", fail_blob_directory)

    with pytest.raises(
        StoreError,
        match=(
            r"Jacobian could not write artifact data\. Check the state directory "
            r"and available disk space, then retry\."
        ),
    ) as raised:
        store.put(
            schema_uri=schema,
            semantics_uri=semantics,
            payload={"unique": "filesystem-error"},
        )
    assert "/private/provider" not in str(raised.value)
    assert "/private/provider" in caplog.text
