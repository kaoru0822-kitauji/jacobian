"""Local searchable research episodes with explicit trust labels."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from jacobian.canonical import canonicalize_json
from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
)
from jacobian.contracts.memory import MemoryHit, MemorySearchResult, ResearchEpisode
from jacobian.schema_registry import SchemaRegistry, model_schema
from jacobian.store import ArtifactStore


class ResearchMemory:
    """Index immutable capability episodes without promoting retrieved content."""

    def __init__(self, store: ArtifactStore, schemas: SchemaRegistry) -> None:
        self.store = store
        self.schemas = schemas
        self.episode_schema_uri = schemas.register(
            name="jacobian.research-episode",
            version="1",
            schema=model_schema(ResearchEpisode),
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
        self._upgrade_legacy_index()

    def _upgrade_legacy_index(self) -> None:
        with self.store.connection() as connection:
            existing = connection.execute(
                """
                SELECT episode_uri, tags_json
                FROM research_episodes
                WHERE episode_uri NOT IN (
                    SELECT episode_uri
                    FROM research_episode_index_versions
                    WHERE index_version = '2'
                )
                """
            ).fetchall()
            for row in existing:
                for tag in json.loads(row["tags_json"]):
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO research_episode_tags(episode_uri, tag)
                        VALUES (?, ?)
                        """,
                        (row["episode_uri"], tag),
                    )
                stored = self.store.get(row["episode_uri"])
                episode = ResearchEpisode.model_validate(stored.payload)
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO research_episode_failures(
                        episode_uri, stage, classification
                    ) VALUES (?, ?, ?)
                    """,
                    (
                        (row["episode_uri"], stage, classification)
                        for stage, classification in _failure_metadata(episode.result)
                    ),
                )
                connection.execute(
                    """
                    INSERT OR REPLACE INTO research_episode_index_versions(
                        episode_uri, index_version
                    ) VALUES (?, '2')
                    """,
                    (row["episode_uri"],),
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
        with self.store.connection() as connection:
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
            connection.executemany(
                """
                INSERT OR IGNORE INTO research_episode_tags(episode_uri, tag)
                VALUES (?, ?)
                """,
                ((stored.artifact_uri, tag) for tag in episode.tags),
            )
            failure_metadata = _failure_metadata(episode.result)
            connection.executemany(
                """
                INSERT OR IGNORE INTO research_episode_failures(
                    episode_uri, stage, classification
                ) VALUES (?, ?, ?)
                """,
                (
                    (stored.artifact_uri, stage, classification)
                    for stage, classification in failure_metadata
                ),
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO research_episode_index_versions(
                    episode_uri, index_version
                ) VALUES (?, '2')
                """,
                (stored.artifact_uri,),
            )
        return stored.artifact_uri

    def search(
        self,
        *,
        query: str = "",
        capability_id: str | None = None,
        domains: tuple[str, ...] = (),
        tags_all: tuple[str, ...] = (),
        tags_any: tuple[str, ...] = (),
        failure_stages: tuple[str, ...] = (),
        failure_classifications: tuple[str, ...] = (),
        assurance_level: CapabilityAssuranceLevel | str | None = None,
        cutoff: datetime | None = None,
        limit: int = 10,
    ) -> MemorySearchResult:
        if len(query) > 512:
            raise ValueError("memory query exceeds 512 characters")
        if not 1 <= limit <= 100:
            raise ValueError("memory search limit must be between 1 and 100")
        _validate_filter_values("domain", domains)
        _validate_filter_values("tag", (*tags_all, *tags_any))
        _validate_filter_values("failure stage", failure_stages)
        _validate_filter_values("failure classification", failure_classifications)
        clauses: list[str] = []
        parameters: list[Any] = []
        terms = [term.casefold() for term in query.split() if term]
        for term in terms:
            clauses.append("search_text LIKE ? ESCAPE '\\'")
            parameters.append(f"%{_escape_like(term)}%")
        if capability_id is not None:
            clauses.append("capability_id = ?")
            parameters.append(capability_id)
        if domains:
            placeholders = ", ".join("?" for _ in domains)
            clauses.append(
                f"""
                CASE
                    WHEN instr(capability_id, '.') > 0
                    THEN substr(capability_id, 1, instr(capability_id, '.') - 1)
                    ELSE capability_id
                END IN ({placeholders})
                """
            )
            parameters.extend(domains)
        for tag in tags_all:
            clauses.append(
                """
                EXISTS (
                    SELECT 1 FROM research_episode_tags tag_match
                    WHERE tag_match.episode_uri = research_episodes.episode_uri
                      AND tag_match.tag = ?
                )
                """
            )
            parameters.append(tag)
        if tags_any:
            placeholders = ", ".join("?" for _ in tags_any)
            clauses.append(
                f"""
                EXISTS (
                    SELECT 1 FROM research_episode_tags tag_match
                    WHERE tag_match.episode_uri = research_episodes.episode_uri
                      AND tag_match.tag IN ({placeholders})
                )
                """
            )
            parameters.extend(tags_any)
        if failure_stages:
            placeholders = ", ".join("?" for _ in failure_stages)
            clauses.append(
                f"""
                EXISTS (
                    SELECT 1 FROM research_episode_failures failure_match
                    WHERE failure_match.episode_uri = research_episodes.episode_uri
                      AND failure_match.stage IN ({placeholders})
                )
                """
            )
            parameters.extend(failure_stages)
        if failure_classifications:
            placeholders = ", ".join("?" for _ in failure_classifications)
            clauses.append(
                f"""
                EXISTS (
                    SELECT 1 FROM research_episode_failures failure_match
                    WHERE failure_match.episode_uri = research_episodes.episode_uri
                      AND failure_match.classification IN ({placeholders})
                )
                """
            )
            parameters.extend(failure_classifications)
        if assurance_level is not None:
            selected = CapabilityAssuranceLevel(assurance_level)
            clauses.append("assurance_level = ?")
            parameters.append(selected.value)
        if cutoff is not None:
            clauses.append("created_at <= ?")
            parameters.append(cutoff.isoformat())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.store.connection() as connection:
            snapshot_rows = connection.execute(
                "SELECT episode_uri FROM research_episodes ORDER BY episode_uri"
            ).fetchall()
            total_matches = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM research_episodes {where}",
                    parameters,
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"""
                SELECT episode_uri, capability_id, mode, assurance_level,
                       summary, tags_json, created_at
                FROM research_episodes
                {where}
                ORDER BY created_at DESC, episode_uri
                LIMIT ?
                """,
                [*parameters, limit],
            ).fetchall()
        snapshot_uris = [row["episode_uri"] for row in snapshot_rows]
        index_snapshot = (
            "sha256:"
            + hashlib.sha256(
                canonicalize_json(
                    {
                        "index_version": "2",
                        "episode_uris": snapshot_uris,
                    }
                )
            ).hexdigest()
        )
        matched_filters = _matched_filter_labels(
            capability_id=capability_id,
            domains=domains,
            tags_all=tags_all,
            tags_any=tags_any,
            failure_stages=failure_stages,
            failure_classifications=failure_classifications,
            assurance_level=assurance_level,
            cutoff=cutoff,
        )
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
                matched_query_terms=tuple(terms),
                matched_filters=matched_filters,
            )
            for row in rows
        )
        return MemorySearchResult(
            query=query,
            hits=hits,
            cutoff=cutoff,
            index_snapshot=index_snapshot,
            indexed_episode_count=len(snapshot_uris),
            total_matches=total_matches,
            returned_count=len(hits),
            truncated=len(hits) < total_matches,
            completeness=("PARTIAL" if len(hits) < total_matches else "COMPLETE"),
        )


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _validate_filter_values(label: str, values: tuple[str, ...]) -> None:
    if len(values) > 32:
        raise ValueError(f"memory search accepts at most 32 {label} filters")
    if len(set(values)) != len(values):
        raise ValueError(f"memory search {label} filters must be unique")
    if any(not value or len(value) > 128 for value in values):
        raise ValueError(
            f"memory search {label} filters must contain 1 to 128 characters"
        )


def _failure_metadata(result: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    metadata: set[tuple[str, str]] = set()
    diagnostics = result.get("diagnostics", ())
    if isinstance(diagnostics, (list, tuple)):
        for diagnostic in diagnostics:
            if not isinstance(diagnostic, dict):
                continue
            stage = diagnostic.get("stage")
            classification = diagnostic.get("code")
            if isinstance(stage, str) and isinstance(classification, str):
                metadata.add((stage, classification))
    output = result.get("output")
    if isinstance(output, dict):
        classifications = output.get("failure_classifications", ())
        if isinstance(classifications, (list, tuple)):
            for classification in classifications:
                if isinstance(classification, str):
                    metadata.add(("mathematical_evaluation", classification))
    return tuple(sorted(metadata))


def _matched_filter_labels(
    *,
    capability_id: str | None,
    domains: tuple[str, ...],
    tags_all: tuple[str, ...],
    tags_any: tuple[str, ...],
    failure_stages: tuple[str, ...],
    failure_classifications: tuple[str, ...],
    assurance_level: CapabilityAssuranceLevel | str | None,
    cutoff: datetime | None,
) -> tuple[str, ...]:
    labels: list[str] = []
    if capability_id is not None:
        labels.append("capability_id")
    if domains:
        labels.append("domains")
    if tags_all:
        labels.append("tags_all")
    if tags_any:
        labels.append("tags_any")
    if failure_stages:
        labels.append("failure_stages")
    if failure_classifications:
        labels.append("failure_classifications")
    if assurance_level is not None:
        labels.append("assurance_level")
    if cutoff is not None:
        labels.append("cutoff")
    return tuple(labels)
