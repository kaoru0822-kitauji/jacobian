from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import threading
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from jacobian.canonical import CanonicalizationError
from jacobian.store import (
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    ArtifactStore,
    StoreError,
    StoreLimitError,
    StoreLimits,
    transaction_active_for,
)


def test_transaction_commits_multiple_descriptors_together(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)

    with store.transaction():
        first = store.register_descriptor(
            kind="schema",
            name="example.first",
            version="1",
            definition={"type": "object"},
        )
        second = store.register_descriptor(
            kind="semantics",
            name="example.second",
            version="1",
            definition={"description": "second"},
        )

    assert (
        store.get_descriptor(first, expected_kind="schema")["name"] == "example.first"
    )
    assert (
        store.get_descriptor(second, expected_kind="semantics")["name"]
        == "example.second"
    )
    assert not store.transaction_recovery_path.exists()


def test_metadata_connections_use_full_synchronous_durability(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    with store.connection() as connection:
        synchronous = connection.execute("PRAGMA synchronous").fetchone()
    assert synchronous is not None
    assert synchronous[0] == 2


@pytest.mark.skipif(os.name == "nt", reason="Windows has no directory fsync")
def test_transaction_batches_blob_directory_syncs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ArtifactStore(tmp_path)
    payloads_by_prefix: dict[str, list[bytes]] = {}
    value = 0
    while not any(len(payloads) == 2 for payloads in payloads_by_prefix.values()):
        payload = value.to_bytes(2, "big")
        prefix = sha256(payload).hexdigest()[:2]
        payloads_by_prefix.setdefault(prefix, []).append(payload)
        value += 1
    payloads = next(
        payloads for payloads in payloads_by_prefix.values() if len(payloads) == 2
    )
    synced: list[Path] = []
    real_sync_directory = store._sync_directory

    def record_sync(directory: Path) -> None:
        if directory == store.root:
            real_sync_directory(directory)
            return
        synced.append(directory)
        real_sync_directory(directory)

    monkeypatch.setattr(store, "_sync_directory", record_sync)
    with store.transaction():
        first_digest = store._write_blob(payloads[0])
        store._write_blob(payloads[1])
        assert synced == []
        assert store.transaction_recovery_path.exists()

    assert synced == [store._blob_path(first_digest).parent, store.blob_root]


@pytest.mark.skipif(os.name == "nt", reason="Windows has no directory fsync")
def test_transaction_body_failure_flushes_before_reconciliation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ArtifactStore(tmp_path)
    real_sync_directory = store._sync_directory
    synced: list[Path] = []

    def record_sync(directory: Path) -> None:
        if directory != store.root:
            synced.append(directory)
        real_sync_directory(directory)

    monkeypatch.setattr(store, "_sync_directory", record_sync)
    descriptor_uri = ""
    with (
        pytest.raises(RuntimeError, match="abort transaction"),
        store.transaction(),
    ):
        descriptor_uri = store.register_descriptor(
            kind="schema",
            name="example.body-failure",
            version="1",
            definition={"type": "object"},
        )
        raise RuntimeError("abort transaction")

    assert synced
    assert synced[-1] == store.blob_root
    assert not store.transaction_recovery_path.exists()
    with pytest.raises(ArtifactNotFoundError):
        store.get_descriptor(descriptor_uri, expected_kind="schema")


@pytest.mark.skipif(os.name == "nt", reason="Windows has no directory fsync")
def test_persistent_directory_sync_failure_poisoned_until_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ArtifactStore(tmp_path)
    real_sync_directory = store._sync_directory

    def fail_blob_prefix_sync(directory: Path) -> None:
        if directory.parent == store.blob_root:
            raise OSError("persistent directory sync failure")
        real_sync_directory(directory)

    monkeypatch.setattr(store, "_sync_directory", fail_blob_prefix_sync)
    with (
        pytest.raises(StoreError, match="reopen the store to recover"),
        store.transaction(),
    ):
        store.register_descriptor(
            kind="schema",
            name="example.persistent-sync-failure",
            version="1",
            definition={"type": "object"},
        )

    assert store.transaction_recovery_path.exists()
    assert not store.transaction_active
    assert not transaction_active_for(store.db_path)
    with pytest.raises(StoreError, match="requires recovery"):
        store.register_descriptor(
            kind="schema",
            name="example.poisoned",
            version="1",
            definition={"type": "object"},
        )
    recovered = ArtifactStore(tmp_path)
    assert not recovered.transaction_recovery_path.exists()


@pytest.mark.skipif(os.name == "nt", reason="Windows has no directory fsync")
def test_recovery_sync_failure_leaves_marker_for_later_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ArtifactStore(tmp_path)
    real_sync_directory = ArtifactStore._sync_directory

    def fail_blob_prefix_sync(self: ArtifactStore, directory: Path) -> None:
        if directory.parent == self.blob_root:
            raise OSError("persistent recovery sync failure")
        real_sync_directory(self, directory)

    monkeypatch.setattr(ArtifactStore, "_sync_directory", fail_blob_prefix_sync)
    with (
        pytest.raises(StoreError, match="reopen the store to recover"),
        store.transaction(),
    ):
        store.register_descriptor(
            kind="schema",
            name="example.failed-publication-sync",
            version="1",
            definition={"type": "object"},
        )
    assert store.transaction_recovery_path.exists()
    with pytest.raises(OSError, match="persistent recovery sync failure"):
        ArtifactStore(tmp_path)
    assert store.transaction_recovery_path.exists()
    monkeypatch.setattr(ArtifactStore, "_sync_directory", real_sync_directory)
    assert not ArtifactStore(tmp_path).transaction_recovery_path.exists()


@pytest.mark.skipif(os.name == "nt", reason="Windows has no directory fsync")
def test_preopened_store_recovers_existing_marker_before_new_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed_store = ArtifactStore(tmp_path)
    preopened_store = ArtifactStore(tmp_path)
    real_failed_sync = failed_store._sync_directory

    def fail_blob_prefix_sync(directory: Path) -> None:
        if directory.parent == failed_store.blob_root:
            raise OSError("publication sync failure")
        real_failed_sync(directory)

    monkeypatch.setattr(failed_store, "_sync_directory", fail_blob_prefix_sync)
    with (
        pytest.raises(StoreError, match="reopen the store to recover"),
        failed_store.transaction(),
    ):
        failed_store.register_descriptor(
            kind="schema",
            name="example.preopened-failed",
            version="1",
            definition={"type": "object"},
        )
    assert failed_store.transaction_recovery_path.exists()

    real_write_marker = preopened_store._write_transaction_recovery_marker
    recovered_before_new_marker = False

    def assert_recovered_before_new_marker() -> None:
        nonlocal recovered_before_new_marker
        recovered_before_new_marker = (
            not preopened_store.transaction_recovery_path.exists()
        )
        real_write_marker()

    monkeypatch.setattr(
        preopened_store,
        "_write_transaction_recovery_marker",
        assert_recovered_before_new_marker,
    )
    with preopened_store.transaction():
        descriptor_uri = preopened_store.register_descriptor(
            kind="schema",
            name="example.preopened-recovered",
            version="1",
            definition={"type": "object"},
        )
    assert recovered_before_new_marker
    assert (
        preopened_store.get_descriptor(descriptor_uri, expected_kind="schema")["name"]
        == "example.preopened-recovered"
    )


@pytest.mark.skipif(os.name == "nt", reason="Windows has no directory fsync")
def test_preopened_store_recovers_before_direct_repeated_descriptor_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    failed_store = ArtifactStore(tmp_path)
    preopened_store = ArtifactStore(tmp_path)
    real_failed_sync = failed_store._sync_directory

    def fail_blob_prefix_sync(directory: Path) -> None:
        if directory.parent == failed_store.blob_root:
            raise OSError("publication sync failure")
        real_failed_sync(directory)

    monkeypatch.setattr(failed_store, "_sync_directory", fail_blob_prefix_sync)
    failed_uri = ""
    with (
        pytest.raises(StoreError, match="reopen the store to recover"),
        failed_store.transaction(),
    ):
        failed_uri = failed_store.register_descriptor(
            kind="schema",
            name="example.preopened-direct-repeat",
            version="1",
            definition={"type": "object"},
        )
    assert failed_store.transaction_recovery_path.exists()

    recovery_sync_seen = False
    real_preopened_sync = preopened_store._sync_directory
    real_remove_marker = preopened_store._remove_transaction_recovery_marker

    def observe_recovery_sync(directory: Path) -> None:
        nonlocal recovery_sync_seen
        if directory.parent == preopened_store.blob_root:
            recovery_sync_seen = True
        real_preopened_sync(directory)

    def assert_synced_before_marker_removal() -> None:
        assert recovery_sync_seen
        real_remove_marker()

    monkeypatch.setattr(preopened_store, "_sync_directory", observe_recovery_sync)
    monkeypatch.setattr(
        preopened_store,
        "_remove_transaction_recovery_marker",
        assert_synced_before_marker_removal,
    )
    repeated_uri = preopened_store.register_descriptor(
        kind="schema",
        name="example.preopened-direct-repeat",
        version="1",
        definition={"type": "object"},
    )
    assert repeated_uri == failed_uri
    assert recovery_sync_seen


@pytest.mark.parametrize("failure", ["rollback", "close"])
def test_cleanup_failure_clears_ownership_and_defers_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    store = ArtifactStore(tmp_path)
    real_connect = store._connect
    connection = real_connect()
    closed = False

    class CleanupFailureConnection:
        def __getattr__(self, name: str) -> Any:
            return getattr(connection, name)

        def rollback(self) -> None:
            if failure == "rollback":
                raise sqlite3.OperationalError("simulated rollback failure")
            connection.rollback()

        def close(self) -> None:
            nonlocal closed
            closed = True
            connection.close()
            if failure == "close":
                raise sqlite3.OperationalError("simulated close failure")

    monkeypatch.setattr(store, "_connect", lambda: CleanupFailureConnection())
    with (
        pytest.raises(StoreError, match="cleanup was not durable"),
        store.transaction(),
    ):
        raise RuntimeError("abort transaction")
    assert closed
    assert not store.transaction_active
    assert not transaction_active_for(store.db_path)
    assert store.transaction_recovery_path.exists()
    monkeypatch.setattr(store, "_connect", real_connect)
    with pytest.raises(StoreError, match="requires recovery"):
        store.find_by_object_digest("sha256:" + "0" * 64)
    assert not ArtifactStore(tmp_path).transaction_recovery_path.exists()


@pytest.mark.skipif(os.name == "nt", reason="Windows has no directory fsync")
def test_markerless_direct_sync_failure_is_synced_before_quota_clearance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ArtifactStore(tmp_path)
    real_store_sync = store._sync_directory

    def fail_blob_prefix_sync(directory: Path) -> None:
        if directory.parent == store.blob_root:
            raise OSError("direct publication sync failure")
        real_store_sync(directory)

    monkeypatch.setattr(store, "_sync_directory", fail_blob_prefix_sync)
    with pytest.raises(StoreError, match="could not write artifact data"):
        store.register_descriptor(
            kind="schema",
            name="example.markerless-sync-failure",
            version="1",
            definition={"type": "object"},
        )
    assert not store.transaction_recovery_path.exists()
    with sqlite3.connect(store.db_path) as connection:
        required_before_reopen = connection.execute(
            "SELECT reconciliation_required FROM blob_quota WHERE id = 0"
        ).fetchone()
    assert required_before_reopen == (1,)

    real_sync_directory = ArtifactStore._sync_directory
    observed_prefix_sync = False

    def assert_quota_still_requires_recovery(
        self: ArtifactStore, directory: Path
    ) -> None:
        nonlocal observed_prefix_sync
        if directory.parent == self.blob_root:
            with sqlite3.connect(self.db_path) as connection:
                row = connection.execute(
                    "SELECT reconciliation_required FROM blob_quota WHERE id = 0"
                ).fetchone()
            assert row == (1,)
            observed_prefix_sync = True
        real_sync_directory(self, directory)

    monkeypatch.setattr(
        ArtifactStore, "_sync_directory", assert_quota_still_requires_recovery
    )
    recovered = ArtifactStore(tmp_path)
    assert observed_prefix_sync
    assert recovered._blob_bytes_committed() > 0
    with recovered.connection() as connection:
        required_after_reopen = connection.execute(
            "SELECT reconciliation_required FROM blob_quota WHERE id = 0"
        ).fetchone()
    assert required_after_reopen is not None
    assert required_after_reopen[0] == 0


def test_transactions_serialize_across_store_instances(tmp_path: Path) -> None:
    first = ArtifactStore(tmp_path)
    second = ArtifactStore(tmp_path)
    writer_started = threading.Event()
    writer_entered = threading.Event()

    def write_from_second_store() -> None:
        writer_started.set()
        with second.transaction():
            writer_entered.set()
            second.register_descriptor(
                kind="schema",
                name="example.concurrent",
                version="1",
                definition={"type": "object"},
            )

    writer = threading.Thread(target=write_from_second_store)
    with first.transaction():
        first.register_descriptor(
            kind="schema",
            name="example.serialized",
            version="1",
            definition={"type": "object"},
        )
        writer.start()
        assert writer_started.wait(timeout=5)
        assert not writer_entered.wait(timeout=0.1)

    writer.join(timeout=5)
    assert not writer.is_alive()
    assert writer_entered.is_set()


def test_transaction_rolls_back_metadata_and_recovers_blob_accounting(
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path)
    descriptor_uri = ""

    with pytest.raises(RuntimeError, match="abort bootstrap"), store.transaction():
        descriptor_uri = store.register_descriptor(
            kind="schema",
            name="example.rolled-back",
            version="1",
            definition={"type": "object"},
        )
        raise RuntimeError("abort bootstrap")

    with pytest.raises(ArtifactNotFoundError):
        store.get_descriptor(descriptor_uri, expected_kind="schema")

    stored_blob_bytes = sum(
        blob.stat().st_size
        for prefix in store.blob_root.iterdir()
        if prefix.is_dir()
        for blob in prefix.iterdir()
        if blob.is_file()
    )
    assert store._blob_bytes_committed() == stored_blob_bytes

    committed = store.register_descriptor(
        kind="schema",
        name="example.after-rollback",
        version="1",
        definition={"type": "object"},
    )
    assert (
        store.get_descriptor(committed, expected_kind="schema")["name"]
        == "example.after-rollback"
    )


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


def test_repeated_put_validates_without_blob_or_metadata_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    expected = store.put(
        schema_uri=schema,
        semantics_uri=semantics,
        payload={"value": "unchanged"},
        summary="candidate",
    )

    original_connect = store._connect

    def connect_read_only() -> sqlite3.Connection:
        connection = original_connect()

        def deny_metadata_writes(
            action: int,
            _argument_one: str | None,
            _argument_two: str | None,
            _database: str | None,
            _trigger: str | None,
        ) -> int:
            if action in {
                sqlite3.SQLITE_DELETE,
                sqlite3.SQLITE_INSERT,
                sqlite3.SQLITE_UPDATE,
            }:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        connection.set_authorizer(deny_metadata_writes)
        return connection

    monkeypatch.setattr(store, "_connect", connect_read_only)

    def reject_blob_write(_data: bytes) -> str:
        pytest.fail("an idempotent put must not publish blobs")

    monkeypatch.setattr(store, "_write_blob", reject_blob_write)

    repeated = store.put(
        schema_uri=schema,
        semantics_uri=semantics,
        payload={"value": "unchanged"},
        summary="candidate",
    )

    assert repeated == expected


def test_repeated_put_rejects_corrupted_committed_blob(tmp_path: Path) -> None:
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
    store.put(
        schema_uri=schema,
        semantics_uri=semantics,
        payload={"value": "original"},
    )
    payload_path = next(
        path
        for path in (tmp_path / "blobs" / "sha256").glob("*/*")
        if path.read_bytes() == b'{"value":"original"}'
    )
    payload_path.write_bytes(b'{"value":"tampered"}')

    with pytest.raises(ArtifactIntegrityError, match="blob digest mismatch"):
        store.put(
            schema_uri=schema,
            semantics_uri=semantics,
            payload={"value": "original"},
        )


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
    second_started = threading.Event()
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

    def commit(data: bytes, *, started: threading.Event | None = None) -> None:
        if started is not None:
            started.set()
        try:
            outcomes.append(store._write_blob(data))
        except Exception as exc:
            outcomes.append(exc)

    first = threading.Thread(target=commit, args=(b"a" * 600,))
    second = threading.Thread(
        target=commit,
        args=(b"b" * 600,),
        kwargs={"started": second_started},
    )
    first.start()
    assert first_accounting.wait(timeout=1)
    second.start()
    assert second_started.wait(timeout=1)

    release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    with call_lock:
        assert accounting_calls == 2
    assert sum(isinstance(outcome, str) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, StoreLimitError) for outcome in outcomes) == 1


def test_blob_writes_do_not_rescan_the_blob_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ArtifactStore(tmp_path)

    def unexpected_scan(_path: Path) -> None:
        raise AssertionError("blob writes must use durable quota accounting")

    monkeypatch.setattr(Path, "iterdir", unexpected_scan)
    store._write_blob(b"constant-time quota accounting")


def test_store_open_reconciles_stale_quota_metadata(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    committed = store._blob_bytes_committed()
    store._adjust_blob_bytes_committed(
        512,
        reconciliation_required=True,
    )

    reopened = ArtifactStore(tmp_path)

    assert reopened._blob_bytes_committed() == committed


def test_store_open_migrates_legacy_quota_metadata(tmp_path: Path) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    database = tmp_path / "metadata.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE blob_quota (
                id INTEGER PRIMARY KEY CHECK (id = 0),
                size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0)
            )
            """
        )
        connection.execute("INSERT INTO blob_quota (id, size_bytes) VALUES (0, 999)")

    store = ArtifactStore(tmp_path)

    with sqlite3.connect(database) as connection:
        columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(blob_quota)")
        }
        row = connection.execute(
            """
            SELECT size_bytes, reconciliation_required
            FROM blob_quota
            WHERE id = 0
            """
        ).fetchone()
    assert "reconciliation_required" in columns
    assert row == (0, 0)
    assert store._blob_bytes_committed() == 0


def test_concurrent_store_open_migrates_legacy_quota_metadata_once(
    tmp_path: Path,
) -> None:
    tmp_path.mkdir(parents=True, exist_ok=True)
    database = tmp_path / "metadata.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE blob_quota (
                id INTEGER PRIMARY KEY CHECK (id = 0),
                size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0)
            )
            """
        )
        connection.execute("INSERT INTO blob_quota (id, size_bytes) VALUES (0, 0)")
    script = """
import sys
from jacobian.store import ArtifactStore

ArtifactStore(sys.argv[1])
"""
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(tmp_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    completed = [process.communicate(timeout=30) for process in processes]

    assert [process.returncode for process in processes] == [0, 0], completed
    with sqlite3.connect(database) as connection:
        columns = [
            str(row[1]) for row in connection.execute("PRAGMA table_info(blob_quota)")
        ]
    assert columns.count("reconciliation_required") == 1


def test_store_open_recovers_process_death_before_blob_publication(
    tmp_path: Path,
) -> None:
    script = """
import os
import sys
from jacobian.store import ArtifactStore

store = ArtifactStore(sys.argv[1])
adjust = store._adjust_blob_bytes_committed

def reserve_then_exit(delta, *, reconciliation_required):
    adjust(delta, reconciliation_required=reconciliation_required)
    os._exit(0)

store._adjust_blob_bytes_committed = reserve_then_exit
store._write_blob(b"reserved-but-unpublished")
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    reopened = ArtifactStore(tmp_path)

    assert reopened._blob_bytes_committed() == 0
    assert not tuple((tmp_path / "blobs" / "sha256").glob("*/*"))


def test_store_open_recovers_process_death_after_blob_publication(
    tmp_path: Path,
) -> None:
    data = b"published-before-clean-marker"
    script = """
import os
import sys
from jacobian.store import ArtifactStore

store = ArtifactStore(sys.argv[1])
store._mark_blob_quota_reconciled = lambda: os._exit(0)
store._write_blob(sys.argv[2].encode("ascii"))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), data.decode("ascii")],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    reopened = ArtifactStore(tmp_path)
    digest = f"sha256:{sha256(data).hexdigest()}"

    assert reopened._blob_bytes_committed() == len(data)
    assert reopened._read_blob(digest) == data


def test_store_open_recovers_process_death_during_store_transaction(
    tmp_path: Path,
) -> None:
    ArtifactStore(tmp_path)
    script = """
import os
import sys
from jacobian.store import ArtifactStore

store = ArtifactStore(sys.argv[1])
with store.transaction():
    store.register_descriptor(
        kind="schema",
        name="crashed.transaction",
        version="1",
        definition={"type": "object", "description": "published before crash"},
    )
    os._exit(0)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / ".transaction-recovery").is_file()

    reopened = ArtifactStore(tmp_path)
    stored_blob_bytes = sum(
        blob.stat().st_size
        for prefix in reopened.blob_root.iterdir()
        if prefix.is_dir()
        for blob in prefix.iterdir()
        if blob.is_file()
    )

    assert reopened._blob_bytes_committed() == stored_blob_bytes
    assert not reopened.transaction_recovery_path.exists()


@pytest.mark.skipif(
    os.name == "nt",
    reason="Windows revalidates blob accounting on every store open",
)
def test_clean_store_open_does_not_scan_the_blob_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ArtifactStore(tmp_path)
    data = b"validated once per unchanged blob"
    digest = store._write_blob(data)

    def unexpected_scan(_path: Path) -> None:
        raise AssertionError("clean store startup must trust durable quota metadata")

    monkeypatch.setattr(Path, "iterdir", unexpected_scan)

    reopened = ArtifactStore(tmp_path)

    assert reopened._blob_bytes_committed() == len(data)
    assert reopened._blob_path(digest).is_file()


def test_duplicate_put_rechecks_a_changed_blob(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    original = b"original"
    digest = store._write_blob(original)
    store._blob_path(digest).write_bytes(b"tampered")

    with pytest.raises(ArtifactIntegrityError, match="does not match"):
        store._write_blob(original)


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
