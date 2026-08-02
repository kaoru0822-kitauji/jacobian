"""Atomic local content-addressed artifact storage."""

from __future__ import annotations

import sqlite3
from contextlib import suppress
from pathlib import Path

from jacobian.canonical import CanonicalLimits
from jacobian.persistence import (
    PersistenceLock,
    StateDatabase,
    StateDatabaseError,
)
from jacobian.persistence.migrations import (
    CURRENT_STATE_FORMAT_REVISION,
    STATE_MIGRATIONS,
    SUPPORTED_STATE_FLOOR,
)
from jacobian.storage.blobs import BlobPublisher
from jacobian.storage.errors import (
    StorageCorruptionError,
    StorageError,
    UnsupportedStateVersionError,
)
from jacobian.storage.metadata import ArtifactMetadata
from jacobian.storage.models import StorageLimits
from jacobian.storage.transactions import TransactionCoordinator


class ArtifactRepository(TransactionCoordinator, BlobPublisher, ArtifactMetadata):
    """Content-addressed blobs plus immutable SQLite artifact metadata."""

    def __init__(
        self,
        root: str | Path,
        *,
        limits: StorageLimits | None = None,
        canonical_limits: CanonicalLimits | None = None,
        synchronous: str = "FULL",
    ) -> None:
        self.root = Path(root).resolve()
        self.limits = limits or StorageLimits()
        self.canonical_limits = canonical_limits or CanonicalLimits(
            max_input_bytes=self.limits.max_artifact_bytes,
            max_output_bytes=self.limits.max_artifact_bytes,
        )
        normalized_synchronous = synchronous.upper()
        if normalized_synchronous not in {"OFF", "NORMAL", "FULL", "EXTRA"}:
            raise ValueError("synchronous must be one of OFF, NORMAL, FULL, or EXTRA")
        # FULL remains the default: callers must opt into a weaker SQLite
        # synchronization policy explicitly.  This is useful for benchmarks
        # and disposable test stores without silently changing durability.
        self.synchronous = normalized_synchronous
        self.blob_root = self.root / "blobs" / "sha256"
        self.staging_root = self.root / "staging"
        self.db_path = self.root / "metadata.sqlite3"
        self.blob_lock_path = self.root / ".blob-quota.lock"
        self._blob_lock = PersistenceLock(self.blob_lock_path)
        self.transaction_recovery_path = self.root / ".transaction-recovery"
        self._validated_blobs: dict[str, tuple[int, int, int, int, int]] = {}
        self.database = StateDatabase(
            self.db_path,
            synchronous=self.synchronous,
        )
        self._closed = False
        self._recovery_required = False
        self.blob_root.mkdir(parents=True, exist_ok=True)
        self.staging_root.mkdir(parents=True, exist_ok=True)
        try:
            self._reject_unsupported_state_revision()
            self.database.migrate(STATE_MIGRATIONS)
        except UnsupportedStateVersionError:
            with suppress(StateDatabaseError):
                self.database.close(checkpoint=False)
            raise
        except StorageCorruptionError:
            with suppress(StateDatabaseError):
                self.database.close(checkpoint=False)
            raise
        except Exception as exc:
            with suppress(StateDatabaseError):
                self.database.close(checkpoint=False)
            raise StorageError("artifact store schema migration failed") from exc
        self._reconcile_blob_quota()

    def _reject_unsupported_state_revision(self) -> None:
        """Reject old and future ledgers before the migration runner can act."""

        revision = self._read_migration_revision()
        if revision is None:
            format_revision = self._read_state_format_revision()
            if format_revision is not None and (
                format_revision < SUPPORTED_STATE_FLOOR
                or format_revision > CURRENT_STATE_FORMAT_REVISION
            ):
                raise UnsupportedStateVersionError(
                    format_revision,
                    minimum_revision=SUPPORTED_STATE_FLOOR,
                )
            return
        if revision < SUPPORTED_STATE_FLOOR or revision > CURRENT_STATE_FORMAT_REVISION:
            raise UnsupportedStateVersionError(
                revision,
                minimum_revision=SUPPORTED_STATE_FLOOR,
            )
        self._validate_state_format_metadata(revision)

    def _read_migration_revision(self) -> int | None:
        if not self.db_path.exists() or self.db_path.is_dir():
            return None
        try:
            with sqlite3.connect(self.db_path) as connection:
                table = connection.execute(
                    """
                    SELECT 1 FROM sqlite_master
                    WHERE type = 'table' AND name = 'jacobian_schema_migrations'
                    """
                ).fetchone()
                if table is None:
                    return None
                row = connection.execute(
                    "SELECT MAX(revision) FROM jacobian_schema_migrations"
                ).fetchone()
        except sqlite3.DatabaseError:
            return None
        return None if row is None or row[0] is None else int(row[0])

    def _read_state_format_revision(self) -> int | None:
        if not self.db_path.exists() or self.db_path.is_dir():
            return None
        try:
            with sqlite3.connect(self.db_path) as connection:
                table = connection.execute(
                    """
                    SELECT 1 FROM sqlite_master
                    WHERE type = 'table' AND name = 'jacobian_state_format'
                    """
                ).fetchone()
                if table is None:
                    return None
                row = connection.execute(
                    """
                    SELECT format_revision
                    FROM jacobian_state_format
                    WHERE id = 0
                    """
                ).fetchone()
        except sqlite3.DatabaseError:
            return None
        return None if row is None or row[0] is None else int(row[0])

    def _validate_state_format_metadata(self, revision: int) -> None:
        try:
            with sqlite3.connect(self.db_path) as connection:
                format_table = connection.execute(
                    """
                    SELECT 1 FROM sqlite_master
                    WHERE type = 'table' AND name = 'jacobian_state_format'
                    """
                ).fetchone()
                if format_table is None:
                    return
                format_row = connection.execute(
                    """
                    SELECT format_revision
                    FROM jacobian_state_format
                    WHERE id = 0
                    """
                ).fetchone()
        except sqlite3.DatabaseError:
            return
        if format_row is None:
            if revision >= CURRENT_STATE_FORMAT_REVISION:
                raise StorageCorruptionError("state-format metadata record is missing")
            return
        format_revision = int(format_row[0])
        if format_revision < SUPPORTED_STATE_FLOOR:
            raise UnsupportedStateVersionError(
                format_revision,
                minimum_revision=SUPPORTED_STATE_FLOOR,
            )
        if format_revision > CURRENT_STATE_FORMAT_REVISION:
            raise UnsupportedStateVersionError(
                format_revision,
                minimum_revision=SUPPORTED_STATE_FLOOR,
            )
        if (
            revision >= CURRENT_STATE_FORMAT_REVISION
            and format_revision != CURRENT_STATE_FORMAT_REVISION
        ):
            raise StorageCorruptionError(
                "state-format metadata does not match the migration head"
            )
