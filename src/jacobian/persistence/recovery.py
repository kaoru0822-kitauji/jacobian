"""Shared recovery and quarantine helpers for experiment-backed services.

``SearchService`` and ``ExperimentService`` both persist snapshots in SQLite
tables and must recover interrupted rows on startup. The quarantine logic
(isolating a corrupt row as ERROR without blocking unrelated rows) and the
internal-artifact put pattern are identical and extracted here.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from typing import Any

from jacobian.contracts.artifacts import ArtifactPutResult
from jacobian.schema_registry import SchemaRegistry
from jacobian.storage.repository import ArtifactRepository


def quarantine_recovery_snapshot(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    error: Exception,
    *,
    experiments_table: str,
    recovery_table: str,
    detail: str,
    logger: Any,
    logger_message: str,
) -> str:
    """Isolate one corrupt recovery row as ERROR without blocking unrelated rows.

    Parameters
    ----------
    connection:
        Active SQLite connection (inside a transaction).
    row:
        The row containing a corrupt ``snapshot_json`` column.
    experiments_table:
        Name of the experiments table (e.g. ``"search_experiments"``).
    recovery_table:
        Name of the recovery failures table.
    detail:
        Human-readable detail stored in the recovery failure row.
    logger:
        Logger instance for the warning.
    logger_message:
        Warning message template (should contain one ``%s`` for the experiment URI).

    Returns
    -------
    str
        The computed ``sha256:`` snapshot digest, for callers that need to
        record it in additional audit artifacts.
    """

    experiment_uri = str(row["experiment_uri"])
    raw = row["snapshot_json"]
    if isinstance(raw, bytes):
        raw_bytes = raw
    elif isinstance(raw, str):
        raw_bytes = raw.encode("utf-8")
    else:
        raw_bytes = repr(raw).encode("utf-8")
    snapshot_digest = "sha256:" + hashlib.sha256(raw_bytes).hexdigest()
    logger.warning(logger_message, experiment_uri, exc_info=error)
    connection.execute(
        f"UPDATE {experiments_table} SET state = 'ERROR' WHERE experiment_uri = ?",
        (experiment_uri,),
    )
    connection.execute(
        f"INSERT OR REPLACE INTO {recovery_table} "
        "(experiment_uri, detected_at, snapshot_digest, detail) "
        "VALUES (?, ?, ?, ?)",
        (experiment_uri, _now().isoformat(), snapshot_digest, detail),
    )
    return snapshot_digest


def put_internal_artifact(
    store: ArtifactRepository,
    schemas: SchemaRegistry,
    semantics_uri: str,
    *,
    schema_uri: str,
    payload: Any,
    parents: tuple[str, ...] = (),
    summary: str,
) -> ArtifactPutResult:
    """Validate and store runtime-owned internal artifact data.

    Shared by SearchService and ExperimentService to validate the schema,
    check the semantics descriptor, and commit the canonical payload.
    """

    normalized = schemas.validate(schema_uri, payload)
    store.get_descriptor(semantics_uri, expected_kind="semantics")
    return store.put(
        schema_uri=schema_uri,
        semantics_uri=semantics_uri,
        payload=normalized,
        parents=parents,
        summary=summary,
    )


def _now() -> datetime:
    return datetime.now(UTC)
