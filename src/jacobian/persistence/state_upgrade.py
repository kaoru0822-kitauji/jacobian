"""Explicit, idempotent upgrades for data formats inside the state store.

The module is temporary compatibility machinery: remove it, together with the
revision-4 data-upgrade ledger, once the supported state floor advances past
revision 3. Keeping that removal condition here prevents migration branches
from leaking back into repositories or domain services.
"""

from __future__ import annotations

from typing import Any

from jacobian.contracts.memory import PersistedTags, ResearchEpisode
from jacobian.persistence import PersistenceCorruptionError, decode_persisted_model
from jacobian.persistence.migrations import RESEARCH_INDEX_UPGRADE_ID
from jacobian.persistence.research_index import failure_metadata


def upgrade_state_data(store: Any) -> None:
    """Complete the revision-3 research index exactly once.

    The upgrade is deliberately owned by persistence rather than
    :class:`ResearchMemory`. All reads, validation, index writes, and the
    completion ledger share one transaction; an interruption rolls back the
    ledger and makes the next store open retry the upgrade.
    """

    with store.connection() as connection:
        already_complete = connection.execute(
            """
            SELECT 1 FROM jacobian_data_upgrades WHERE upgrade_id = ?
            """,
            (RESEARCH_INDEX_UPGRADE_ID,),
        ).fetchone()
    if already_complete is not None:
        return

    with store.transaction(), store.connection() as connection:
        # Another process may have completed the upgrade between the
        # read-only probe and this transaction. The ledger remains the
        # authority for the one-shot boundary.
        already_complete = connection.execute(
            """
            SELECT 1 FROM jacobian_data_upgrades WHERE upgrade_id = ?
            """,
            (RESEARCH_INDEX_UPGRADE_ID,),
        ).fetchone()
        if already_complete is not None:
            return

        rows = connection.execute(
            """
                SELECT episode_uri, tags_json
                FROM research_episodes
                WHERE episode_uri NOT IN (
                    SELECT episode_uri
                    FROM research_episode_index_versions
                    WHERE index_version = '2'
                )
                ORDER BY episode_uri
                """
        ).fetchall()
        for row in rows:
            _upgrade_episode(store, connection, row)
        connection.execute(
            """
                INSERT INTO jacobian_data_upgrades(upgrade_id)
                VALUES (?)
                """,
            (RESEARCH_INDEX_UPGRADE_ID,),
        )


def _upgrade_episode(store: Any, connection: Any, row: Any) -> None:
    episode_uri = str(row["episode_uri"])
    from jacobian.store import StoreCorruptionError, StoreError

    try:
        tags = decode_persisted_model(
            PersistedTags,
            row["tags_json"],
            record_kind="research_episode",
            record_id=episode_uri,
            field="tags_json",
        ).root
        episode = ResearchEpisode.model_validate(store.get(episode_uri).payload)
        failure_rows = failure_metadata(episode.result)
    except (
        PersistenceCorruptionError,
        StoreError,
        ValueError,
        TypeError,
        KeyError,
    ) as exc:
        raise StoreCorruptionError(exc) from exc

    for tag in tags:
        connection.execute(
            """
            INSERT OR IGNORE INTO research_episode_tags(episode_uri, tag)
            VALUES (?, ?)
            """,
            (episode_uri, tag),
        )
    connection.executemany(
        """
        INSERT OR IGNORE INTO research_episode_failures(
            episode_uri, stage, classification
        ) VALUES (?, ?, ?)
        """,
        (
            (episode_uri, stage, classification)
            for stage, classification in failure_rows
        ),
    )
    connection.execute(
        """
        INSERT OR REPLACE INTO research_episode_index_versions(
            episode_uri, index_version
        ) VALUES (?, '2')
        """,
        (episode_uri,),
    )


__all__ = ["RESEARCH_INDEX_UPGRADE_ID", "upgrade_state_data"]
