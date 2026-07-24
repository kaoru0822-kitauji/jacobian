"""Local searchable research episodes with explicit trust labels."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
)
from jacobian.contracts.memory import MemoryHit, MemorySearchResult, ResearchEpisode
from jacobian.schema_registry import SchemaRegistry
from jacobian.store import ArtifactStore


class ResearchMemory:
    """Index immutable capability episodes without promoting retrieved content."""

    def __init__(self, store: ArtifactStore, schemas: SchemaRegistry) -> None:
        self.store = store
        self.schemas = schemas
        self.episode_schema_uri = schemas.register(
            name="jacobian.research-episode",
            version="1",
            schema=ResearchEpisode.model_json_schema(),
        )
        self.episode_semantics_uri = store.register_descriptor(
            kind="semantics",
            name="jacobian.research-episode",
            version="1",
            definition={
                "description": (
                    "trust-labeled model and tool activity; retrieval never promotes "
                    "mathematical assurance"
                )
            },
        )
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.store.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS research_episodes (
                    episode_uri TEXT PRIMARY KEY,
                    capability_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    assurance_level TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    search_text TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS research_episodes_lookup
                ON research_episodes(capability_id, assurance_level, created_at)
                """
            )

    def record(self, episode: ResearchEpisode) -> str:
        normalized = self.schemas.validate(
            self.episode_schema_uri,
            episode.model_dump(mode="json"),
        )
        stored = self.store.put(
            schema_uri=self.episode_schema_uri,
            semantics_uri=self.episode_semantics_uri,
            payload=normalized,
            parents=tuple(
                dict.fromkeys(
                    (
                        *episode.artifact_uris,
                        *(
                            (episode.verification_record_uri,)
                            if episode.verification_record_uri is not None
                            else ()
                        ),
                    )
                )
            ),
            summary=episode.summary,
        )
        search_text = " ".join(
            (
                episode.capability_id,
                episode.summary,
                " ".join(episode.tags),
                json.dumps(episode.request, sort_keys=True),
                json.dumps(episode.result, sort_keys=True),
            )
        ).casefold()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO research_episodes(
                    episode_uri,
                    capability_id,
                    mode,
                    assurance_level,
                    summary,
                    tags_json,
                    search_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stored.artifact_uri,
                    episode.capability_id,
                    episode.mode.value,
                    episode.assurance_level.value,
                    episode.summary,
                    json.dumps(list(episode.tags), sort_keys=True),
                    search_text,
                ),
            )
        return stored.artifact_uri

    def search(
        self,
        *,
        query: str = "",
        capability_id: str | None = None,
        assurance_level: CapabilityAssuranceLevel | str | None = None,
        cutoff: datetime | None = None,
        limit: int = 10,
    ) -> MemorySearchResult:
        if len(query) > 512:
            raise ValueError("memory query exceeds 512 characters")
        if not 1 <= limit <= 100:
            raise ValueError("memory search limit must be between 1 and 100")
        clauses: list[str] = []
        parameters: list[Any] = []
        terms = [term.casefold() for term in query.split() if term]
        for term in terms:
            clauses.append("search_text LIKE ? ESCAPE '\\'")
            parameters.append(f"%{_escape_like(term)}%")
        if capability_id is not None:
            clauses.append("capability_id = ?")
            parameters.append(capability_id)
        if assurance_level is not None:
            selected = CapabilityAssuranceLevel(assurance_level)
            clauses.append("assurance_level = ?")
            parameters.append(selected.value)
        if cutoff is not None:
            clauses.append("created_at <= ?")
            parameters.append(cutoff.isoformat())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        parameters.append(limit)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT episode_uri, capability_id, mode, assurance_level,
                       summary, tags_json, created_at
                FROM research_episodes
                {where}
                ORDER BY created_at DESC, episode_uri
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        hits = tuple(
            MemoryHit(
                episode_uri=row["episode_uri"],
                capability_id=row["capability_id"],
                mode=CapabilityMode(row["mode"]),
                assurance_level=CapabilityAssuranceLevel(row["assurance_level"]),
                summary=row["summary"],
                tags=tuple(json.loads(row["tags_json"])),
                created_at=datetime.fromisoformat(row["created_at"]),
                score=(1000 if terms else 500),
            )
            for row in rows
        )
        return MemorySearchResult(query=query, hits=hits, cutoff=cutoff)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
