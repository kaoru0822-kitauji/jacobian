from __future__ import annotations

import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from jacobian.store import ArtifactStore


def test_store_reuses_one_connection_per_thread(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls = 0
    real_connect = sqlite3.connect

    def counting_connect(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", counting_connect)
    store = ArtifactStore(tmp_path)
    for index in range(12):
        store.register_descriptor(
            kind="schema",
            name=f"component.connection-{index}",
            version="1",
            definition={"type": "object"},
        )

    # Initialization owns the pooled connection.  close() briefly opens one
    # checkpoint connection, so no operation should create a per-query swarm.
    assert calls <= 2
    store.close()


def test_store_closes_connections_owned_by_worker_threads(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    barrier = threading.Barrier(3)
    with ThreadPoolExecutor(max_workers=3) as workers:
        list(workers.map(lambda _: _read_store(store, barrier), range(3)))

    # The connection cache is thread-local, while lifecycle ownership remains
    # explicit at the store.  Worker thread-local objects disappear when the
    # pool exits, but their SQLite handles must still be closed by store.close.
    assert len(store._open_connections) >= 4  # bootstrap + one per worker
    store.close()
    assert not store._open_connections


def _read_store(store: ArtifactStore, barrier: threading.Barrier) -> None:
    barrier.wait()
    with store.connection() as connection:
        connection.execute("SELECT 1").fetchone()


def test_synchronous_policy_is_explicit_and_defaults_to_full(tmp_path: Path) -> None:
    durable = ArtifactStore(tmp_path / "durable")
    with durable.connection() as connection:
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 2
    durable.close()

    disposable = ArtifactStore(tmp_path / "disposable", synchronous="NORMAL")
    with disposable.connection() as connection:
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 1
    disposable.close()
