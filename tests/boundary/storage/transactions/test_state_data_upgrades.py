"""One-shot data upgrades at the persisted-state boundary."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from jacobian.contracts.capabilities import CapabilityAssuranceLevel, CapabilityMode
from jacobian.contracts.memory import ResearchEpisode
from jacobian.memory import ResearchMemory
from jacobian.persistence import state_upgrade
from jacobian.schema_registry import SchemaRegistry
from jacobian.store import (
    ArtifactStore,
    StoreCorruptionError,
    StoreError,
    UnsupportedStateVersionError,
)


def _record_episode(root: Path, *, suffix: str = "") -> str:
    with ArtifactStore(root) as store:
        memory = ResearchMemory(store, SchemaRegistry(store))
        return memory.record(
            ResearchEpisode(
                capability_id="test.memory_upgrade",
                capability_version="1",
                mode=CapabilityMode.EXPLORE,
                request={"case": suffix or "one"},
                result={
                    "diagnostics": [
                        {"stage": "process", "code": "TIMEOUT"},
                    ]
                },
                assurance_level=CapabilityAssuranceLevel.COMPUTED,
                summary="upgrade fixture",
                tags=("fixture", suffix or "one"),
            )
        )


def _connection(root: Path) -> sqlite3.Connection:
    return sqlite3.connect(root / "metadata.sqlite3")


def _remove_index_and_upgrade_ledger(root: Path, episode_uris: tuple[str, ...]) -> None:
    connection = _connection(root)
    try:
        for episode_uri in episode_uris:
            connection.execute(
                "DELETE FROM research_episode_tags WHERE episode_uri = ?",
                (episode_uri,),
            )
            connection.execute(
                "DELETE FROM research_episode_failures WHERE episode_uri = ?",
                (episode_uri,),
            )
            connection.execute(
                "DELETE FROM research_episode_index_versions WHERE episode_uri = ?",
                (episode_uri,),
            )
        connection.execute("DELETE FROM jacobian_data_upgrades")
        connection.commit()
    finally:
        connection.close()


def test_revision_three_data_upgrade_rebuilds_research_index_once(
    tmp_path: Path,
) -> None:
    episode_uri = _record_episode(tmp_path)
    _remove_index_and_upgrade_ledger(tmp_path, (episode_uri,))

    with ArtifactStore(tmp_path):
        pass

    connection = _connection(tmp_path)
    try:
        assert connection.execute(
            "SELECT tag FROM research_episode_tags WHERE episode_uri = ? ORDER BY tag",
            (episode_uri,),
        ).fetchall() == [("fixture",), ("one",)]
        assert connection.execute(
            """
            SELECT stage, classification
            FROM research_episode_failures
            WHERE episode_uri = ?
            """,
            (episode_uri,),
        ).fetchall() == [("process", "TIMEOUT")]
        assert connection.execute(
            """
            SELECT index_version
            FROM research_episode_index_versions
            WHERE episode_uri = ?
            """,
            (episode_uri,),
        ).fetchone() == ("2",)
        assert connection.execute(
            "SELECT COUNT(*) FROM jacobian_data_upgrades"
        ).fetchone() == (1,)
    finally:
        connection.close()


def test_corrupt_research_episode_aborts_upgrade_without_completion(
    tmp_path: Path,
) -> None:
    episode_uri = _record_episode(tmp_path)
    _remove_index_and_upgrade_ledger(tmp_path, (episode_uri,))
    connection = _connection(tmp_path)
    try:
        connection.execute(
            "UPDATE research_episodes SET tags_json = ? WHERE episode_uri = ?",
            (b"not-json", episode_uri),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(StoreCorruptionError):
        ArtifactStore(tmp_path)

    connection = _connection(tmp_path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM jacobian_data_upgrades"
        ).fetchone() == (0,)
    finally:
        connection.close()


def test_interrupted_data_upgrade_rolls_back_and_retries(tmp_path: Path) -> None:
    first = _record_episode(tmp_path, suffix="first")
    second = _record_episode(tmp_path, suffix="second")
    _remove_index_and_upgrade_ledger(tmp_path, (first, second))

    original = state_upgrade._upgrade_episode
    calls = 0

    def fail_after_first(store: object, connection: object, row: object) -> None:
        nonlocal calls
        calls += 1
        original(store, connection, row)
        if calls == 1:
            raise RuntimeError("injected data-upgrade failure")

    state_upgrade._upgrade_episode = fail_after_first
    try:
        with pytest.raises(StoreError, match="schema migration failed"):
            ArtifactStore(tmp_path)
    finally:
        state_upgrade._upgrade_episode = original

    connection = _connection(tmp_path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM jacobian_data_upgrades"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT COUNT(*) FROM research_episode_index_versions"
        ).fetchone() == (0,)
    finally:
        connection.close()

    with ArtifactStore(tmp_path):
        pass

    connection = _connection(tmp_path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM jacobian_data_upgrades"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT COUNT(*) FROM research_episode_index_versions"
        ).fetchone() == (2,)
    finally:
        connection.close()


@pytest.mark.parametrize("revision", [1, 2])
def test_state_below_supported_floor_fails_closed(
    tmp_path: Path,
    revision: int,
) -> None:
    with ArtifactStore(tmp_path):
        pass
    connection = _connection(tmp_path)
    try:
        connection.execute(
            "DELETE FROM jacobian_schema_migrations WHERE revision > ?",
            (revision,),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(UnsupportedStateVersionError) as exc_info:
        ArtifactStore(tmp_path)
    assert exc_info.value.detected_revision == revision
    assert exc_info.value.minimum_revision == 3


@pytest.mark.parametrize("ledger_state", ["missing", "empty"])
def test_future_state_format_metadata_without_ledger_fails_closed(
    tmp_path: Path,
    ledger_state: str,
) -> None:
    with ArtifactStore(tmp_path):
        pass
    connection = _connection(tmp_path)
    try:
        if ledger_state == "missing":
            connection.execute("DROP TABLE jacobian_schema_migrations")
        else:
            connection.execute("DELETE FROM jacobian_schema_migrations")
        connection.execute(
            "UPDATE jacobian_state_format SET format_revision = 99 WHERE id = 0"
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(UnsupportedStateVersionError) as exc_info:
        ArtifactStore(tmp_path)
    assert exc_info.value.detected_revision == 99


def test_research_memory_constructor_does_not_run_data_upgrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with ArtifactStore(tmp_path) as store:
        schemas = SchemaRegistry(store)

        def fail(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("data upgrades belong to ArtifactStore startup")

        monkeypatch.setattr(state_upgrade, "upgrade_state_data", fail)
        ResearchMemory(store, schemas)
