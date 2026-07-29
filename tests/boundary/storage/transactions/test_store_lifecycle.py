"""Behavioral audit of :class:`ArtifactStore` lifecycle ownership.

These tests pin the runtime ownership contract of the local content-addressed
store: explicit ``close``, idempotence, context-manager semantics, WAL/SHM
cleanup, use-after-close rejection, and partial-bootstrap failure recovery.

The contract is verified through observable use-after-close behavior and
on-disk state rather than private ``_closed`` flags wherever possible.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from jacobian.store import (
    ArtifactStore,
    StoreClosedError,
    StoreError,
)


def _wal_files(root: Path) -> list[Path]:
    database = root / "metadata.sqlite3"
    return [
        path
        for path in (
            database.with_name(f"{database.name}-wal"),
            database.with_name(f"{database.name}-shm"),
        )
        if path.exists()
    ]


def test_close_is_idempotent(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)

    store.close()
    # A second close must not raise and must remain a no-op: the store stays
    # closed and operations against it still fail closed.
    store.close()
    with pytest.raises(StoreClosedError):
        store.register_descriptor(
            kind="schema",
            name="after-double-close",
            version="1",
            definition={"type": "object"},
        )


def test_close_during_active_transaction_raises_and_keeps_store_open(
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path)

    with store.transaction():
        with pytest.raises(StoreError, match="cannot close"):
            store.close()
        # The store remains open and the transaction is still usable: a
        # descriptor committed inside the surviving transaction must succeed.
        assert store.transaction_active is True
        store.register_descriptor(
            kind="schema",
            name="example.in-transaction",
            version="1",
            definition={"type": "object"},
        )

    # After the transaction commits, close succeeds and the store is closed.
    store.close()
    with pytest.raises(StoreClosedError):
        store.register_descriptor(
            kind="schema",
            name="after-transaction-close",
            version="1",
            definition={"type": "object"},
        )


def test_context_manager_closes_store(tmp_path: Path) -> None:
    with ArtifactStore(tmp_path) as store:
        # While open the store is usable.
        store.register_descriptor(
            kind="schema",
            name="example.in-context",
            version="1",
            definition={"type": "object"},
        )
    # After the context manager exits the store is closed.
    with pytest.raises(StoreClosedError):
        store.register_descriptor(
            kind="schema",
            name="after-context",
            version="1",
            definition={"type": "object"},
        )


def test_context_manager_exit_suppresses_no_exception(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    with pytest.raises(ValueError, match="body failure"), store:
        raise ValueError("body failure")
    # The store is still closed even though the body raised.
    with pytest.raises(StoreClosedError):
        store.register_descriptor(
            kind="schema",
            name="after-body-failure",
            version="1",
            definition={"type": "object"},
        )


def test_enter_on_closed_store_raises(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.close()

    with pytest.raises(StoreClosedError), store:
        pytest.fail("entering a closed store must not succeed")


def test_use_after_close_rejects_operations(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.close()

    with pytest.raises(StoreClosedError), store.connection():
        pass
    with pytest.raises(StoreClosedError):
        store.put(
            schema_uri="artifact://sha256/" + "0" * 64,
            semantics_uri="artifact://sha256/" + "1" * 64,
            payload={"value": "after-close"},
        )
    with pytest.raises(StoreClosedError):
        store.get("artifact://sha256/" + "0" * 64)
    with pytest.raises(StoreClosedError):
        store.register_descriptor(
            kind="schema",
            name="after-close",
            version="1",
            definition={"type": "object"},
        )


def test_transaction_on_closed_store_rejects_without_side_effects(
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path)
    store.close()

    assert not store.transaction_recovery_path.exists()
    with pytest.raises(StoreClosedError), store.transaction():
        pytest.fail("a closed store must not begin a transaction")

    # Rejecting the transaction must not leave a stale recovery marker behind.
    # A stale marker forces an unnecessary full blob-tree rescan on the next
    # store open, so this is a real ownership defect when it occurs.
    assert not store.transaction_recovery_path.exists()
    assert not store.transaction_active


def test_close_checkpoints_wal_to_empty(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    store.register_descriptor(
        kind="schema",
        name="example.checkpoint",
        version="1",
        definition={"type": "object"},
    )

    store.close()

    wal = store.db_path.with_name(f"{store.db_path.name}-wal")
    if wal.exists():
        # A checkpointed WAL is truncated to zero bytes.
        assert wal.stat().st_size == 0


def test_close_leaves_database_consistent(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    descriptor = store.register_descriptor(
        kind="schema",
        name="example.durable",
        version="1",
        definition={"type": "object"},
    )
    store.close()

    # A fresh connection against the closed store's database must see the
    # committed descriptor; close must not lose committed metadata.
    with sqlite3.connect(store.db_path) as connection:
        row = connection.execute(
            "SELECT artifact_uri FROM artifacts WHERE artifact_uri = ?",
            (descriptor,),
        ).fetchone()
    assert row is not None


def test_repeated_close_after_context_manager_is_idempotent(
    tmp_path: Path,
) -> None:
    with ArtifactStore(tmp_path) as store:
        store.register_descriptor(
            kind="schema",
            name="example.lifecycle",
            version="1",
            definition={"type": "object"},
        )
    # Explicit close after the context manager already closed the store.
    store.close()
    with pytest.raises(StoreClosedError):
        store.register_descriptor(
            kind="schema",
            name="after-repeated-close",
            version="1",
            definition={"type": "object"},
        )


def test_reopened_store_after_close_is_usable(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    descriptor = store.register_descriptor(
        kind="schema",
        name="example.reopen",
        version="1",
        definition={"type": "object"},
    )
    store.close()
    assert _wal_files(tmp_path) == [] or all(
        path.stat().st_size == 0 for path in _wal_files(tmp_path)
    )

    reopened = ArtifactStore(tmp_path)
    assert reopened.get_descriptor(descriptor, expected_kind="schema")["name"] == (
        "example.reopen"
    )
    reopened.close()


def test_failed_bootstrap_does_not_leave_recovery_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A store whose constructor fails partway through initialization must not
    # leave a transaction-recovery marker that would force a rescan on reopen.
    original_initialize = ArtifactStore._initialize_database

    def failing_initialize(self: ArtifactStore) -> None:
        original_initialize(self)
        raise RuntimeError("bootstrap failure")

    monkeypatch.setattr(ArtifactStore, "_initialize_database", failing_initialize)

    with pytest.raises(RuntimeError, match="bootstrap failure"):
        ArtifactStore(tmp_path)

    assert not (tmp_path / ".transaction-recovery").exists()
