"""Atomic local content-addressed artifact storage."""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Final

from jacobian.canonical import (
    CanonicalLimits,
    canonicalize_json,
    loads_strict_json,
)
from jacobian.contracts.artifacts import ArtifactManifest, ArtifactPutResult

_OBJECT_FORMAT_VERSION: Final = b"jacobian.object.v1"
_CANONICALIZER_NAME: Final = b"jacobian.rfc8785+nfc+exact-rational.v1"
CANONICALIZER_DIGEST: Final = (
    "sha256:" + hashlib.sha256(_CANONICALIZER_NAME).hexdigest()
)
_LOGGER = logging.getLogger(__name__)

_BOOTSTRAP_SCHEMA_URI: Final = (
    "artifact://sha256/" + hashlib.sha256(b"jacobian.bootstrap.schema.v1").hexdigest()
)
_BOOTSTRAP_SEMANTICS_URI: Final = (
    "artifact://sha256/"
    + hashlib.sha256(b"jacobian.bootstrap.semantics.v1").hexdigest()
)


class StoreError(RuntimeError):
    """Base class for bounded artifact-store failures."""


class ArtifactNotFoundError(StoreError):
    """The requested artifact is not committed in this store."""


class ArtifactIntegrityError(StoreError):
    """Stored bytes do not match their content address."""


class StoreLimitError(StoreError):
    """A bounded store limit would be exceeded."""


class StoreClosedError(StoreError):
    """An operation targeted a store whose runtime ownership has ended."""


@dataclass(frozen=True, slots=True)
class StoreLimits:
    """Local artifact and aggregate blob-size limits."""

    max_artifact_bytes: int = 10 * 1024 * 1024
    max_parents: int = 4096
    max_summary_chars: int = 512
    max_total_blob_bytes: int = 1024 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    """A verified-on-read manifest, payload, and canonical byte sequence."""

    artifact_uri: str
    manifest: ArtifactManifest
    payload: Any
    canonical_bytes: bytes


class _ConnectionState(threading.local):
    """Per-thread ownership for one explicit store transaction."""

    def __init__(self) -> None:
        self.transaction: sqlite3.Connection | None = None
        self.blob_lock_depth = 0
        self.pending_sync_directories: set[Path] = set()


class _ActiveTransactionPaths(threading.local):
    """Database paths transaction-owned by the current thread."""

    def __init__(self) -> None:
        self.paths: set[Path] = set()


_ACTIVE_TRANSACTION_PATHS = _ActiveTransactionPaths()


def transaction_active_for(database_path: str | Path) -> bool:
    """Whether this thread owns a store transaction for one database."""

    return Path(database_path).resolve() in _ACTIVE_TRANSACTION_PATHS.paths


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _uri_from_digest(digest: str) -> str:
    return "artifact://sha256/" + digest.removeprefix("sha256:")


def _digest_from_uri(uri: str) -> str:
    prefix = "artifact://sha256/"
    if not uri.startswith(prefix):
        raise ArtifactNotFoundError(f"invalid artifact URI: {uri!r}")
    value = uri.removeprefix(prefix)
    if len(value) != 64 or any(
        char not in "0123456789abcdef"  # pragma: allowlist secret
        for char in value
    ):
        raise ArtifactNotFoundError(f"invalid artifact URI: {uri!r}")
    return "sha256:" + value


def _framed_digest(tag: bytes, parts: tuple[bytes, ...]) -> str:
    digest = hashlib.sha256()
    digest.update(b"jacobian\x00")
    digest.update(len(tag).to_bytes(8, "big"))
    digest.update(tag)
    for part in parts:
        digest.update(len(part).to_bytes(8, "big"))
        digest.update(part)
    return "sha256:" + digest.hexdigest()


def _lock_file(lock_file: BinaryIO) -> None:
    if os.name == "nt":  # pragma: no cover - exercised in cross-platform CI
        import msvcrt

        lock_file.seek(0)
        if not lock_file.read(1):
            lock_file.seek(0)
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        locking = getattr(msvcrt, "locking")  # noqa: B009
        locking(
            lock_file.fileno(),
            getattr(msvcrt, "LK_LOCK"),  # noqa: B009
            1,
        )
        return

    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)


def _unlock_file(lock_file: BinaryIO) -> None:
    if os.name == "nt":  # pragma: no cover - exercised in cross-platform CI
        import msvcrt

        lock_file.seek(0)
        locking = getattr(msvcrt, "locking")  # noqa: B009
        locking(
            lock_file.fileno(),
            getattr(msvcrt, "LK_UNLCK"),  # noqa: B009
            1,
        )
        return

    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


class ArtifactStore:
    """Content-addressed blobs plus immutable SQLite artifact metadata."""

    def __init__(
        self,
        root: str | Path,
        *,
        limits: StoreLimits | None = None,
        canonical_limits: CanonicalLimits | None = None,
    ) -> None:
        self.root = Path(root).resolve()
        self.limits = limits or StoreLimits()
        self.canonical_limits = canonical_limits or CanonicalLimits(
            max_input_bytes=self.limits.max_artifact_bytes,
            max_output_bytes=self.limits.max_artifact_bytes,
        )
        self.blob_root = self.root / "blobs" / "sha256"
        self.staging_root = self.root / "staging"
        self.db_path = self.root / "metadata.sqlite3"
        self.blob_lock_path = self.root / ".blob-quota.lock"
        self.transaction_recovery_path = self.root / ".transaction-recovery"
        self._validated_blobs: dict[str, tuple[int, int, int, int, int]] = {}
        self._connection_state = _ConnectionState()
        self._closed = False
        self._recovery_required = False
        self.blob_root.mkdir(parents=True, exist_ok=True)
        self.staging_root.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        if self._closed:
            raise StoreClosedError("artifact store is closed")
        if self._recovery_required:
            raise StoreError(
                "artifact store requires recovery by a fresh ArtifactStore instance"
            )
        connection = sqlite3.connect(self.db_path, timeout=30)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
        except BaseException:
            connection.close()
            raise
        return connection

    def close(self) -> None:
        """Checkpoint SQLite and end this store's owned lifetime."""

        if self._closed:
            return
        if self.transaction_active:
            raise StoreError("cannot close an artifact store during a transaction")
        if self._recovery_required:
            self._closed = True
            return
        connection = self._connect()
        try:
            checkpoint = connection.execute(
                "PRAGMA wal_checkpoint(TRUNCATE)"
            ).fetchone()
            if checkpoint is None or checkpoint[0] != 0:
                raise StoreError(f"could not checkpoint artifact store: {checkpoint!r}")
        finally:
            connection.close()
        self._closed = True

    def __enter__(self) -> ArtifactStore:
        if self._closed:
            raise StoreClosedError("artifact store is closed")
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Yield this thread's transaction connection or one owned connection."""

        transaction = self._connection_state.transaction
        if transaction is not None:
            yield transaction
            return

        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @property
    def transaction_active(self) -> bool:
        """Whether this thread is inside an explicit store transaction."""

        return self._connection_state.transaction is not None

    @property
    def transaction_identity(self) -> int | None:
        """Process-local identity of this thread's active transaction."""

        transaction = self._connection_state.transaction
        return None if transaction is None else id(transaction)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Commit related store operations through one SQLite transaction.

        Blob publication remains content-addressed and durable. If metadata
        rolls back, quota accounting is reconciled against the published blob
        set before control returns to the caller.
        """

        if self._closed:
            raise StoreClosedError("artifact store is closed")
        if self._recovery_required:
            raise StoreError(
                "artifact store requires recovery by a fresh ArtifactStore instance"
            )
        if self._connection_state.transaction is not None:
            raise StoreError("nested artifact store transactions are unsupported")

        with self._exclusive_blob_lock():
            try:
                if self.transaction_recovery_path.exists():
                    self._reconcile_blob_quota(force=True)
                self._write_transaction_recovery_marker()
                connection = self._connect()
            except BaseException:
                self._recovery_required = True
                raise
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._connection_state.transaction = connection
                _ACTIVE_TRANSACTION_PATHS.paths.add(self.db_path)
                try:
                    yield
                except BaseException:
                    cleanup_error: BaseException | None = None
                    try:
                        connection.rollback()
                    except BaseException as exc:
                        cleanup_error = exc
                    if cleanup_error is None:
                        try:
                            self._flush_transaction_directories()
                        except BaseException as exc:
                            cleanup_error = exc
                    try:
                        connection.close()
                    except BaseException as exc:
                        cleanup_error = cleanup_error or exc
                    finally:
                        self._clear_transaction_state()
                    if cleanup_error is not None:
                        self._recovery_required = True
                        raise StoreError(
                            "artifact transaction cleanup was not durable; "
                            "reopen the store to recover"
                        ) from cleanup_error
                    try:
                        self._reconcile_blob_quota(force=True)
                    except BaseException:
                        self._recovery_required = True
                        raise
                    raise
                else:
                    try:
                        self._flush_transaction_directories()
                        connection.commit()
                        connection.close()
                    except BaseException as exc:
                        self._recovery_required = True
                        try:
                            connection.close()
                        except BaseException:
                            _LOGGER.exception(
                                "failed to close an uncertain artifact transaction"
                            )
                        raise StoreError(
                            "artifact transaction commit was not durable; "
                            "reopen the store to recover"
                        ) from exc
                    finally:
                        self._clear_transaction_state()
                    try:
                        self._remove_transaction_recovery_marker()
                    except BaseException:
                        self._recovery_required = True
                        raise
            except BaseException:
                if self._connection_state.transaction is not None:
                    try:
                        connection.close()
                    except BaseException:
                        _LOGGER.exception(
                            "failed to close artifact transaction during setup cleanup"
                        )
                    self._clear_transaction_state()
                elif (
                    self.transaction_recovery_path.exists()
                    and not self._recovery_required
                ):
                    try:
                        connection.close()
                    except BaseException:
                        _LOGGER.exception(
                            "failed to close artifact transaction after setup failure"
                        )
                    self._recovery_required = True
                raise

    def _clear_transaction_state(self) -> None:
        """Release process-local ownership even when durable cleanup fails."""

        self._connection_state.transaction = None
        self._connection_state.pending_sync_directories.clear()
        _ACTIVE_TRANSACTION_PATHS.paths.discard(self.db_path)

    def _sync_directory(self, path: Path) -> None:
        if os.name == "nt":  # pragma: no cover - Windows has no directory fsync
            return
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _sync_root_directory(self) -> None:
        self._sync_directory(self.root)

    def _sync_blob_publication_directories(
        self,
        prefix: Path,
        *,
        prefix_created: bool,
    ) -> None:
        directories = self._connection_state.pending_sync_directories
        if self.transaction_active:
            directories.add(prefix)
            if prefix_created:
                directories.add(self.blob_root)
            return

        self._sync_directory(prefix)
        if prefix_created:
            self._sync_directory(self.blob_root)

    def _flush_transaction_directories(self) -> None:
        """Make published blob names durable before committing their metadata."""

        directories = self._connection_state.pending_sync_directories
        for directory in sorted(
            directories,
            key=lambda path: (len(path.parts), str(path)),
            reverse=True,
        ):
            self._sync_directory(directory)
        directories.clear()

    def _write_transaction_recovery_marker(self) -> None:
        with self.transaction_recovery_path.open("wb") as marker:
            marker.write(b"jacobian artifact transaction in progress\n")
            marker.flush()
            os.fsync(marker.fileno())
        self._sync_root_directory()

    def _remove_transaction_recovery_marker(self) -> None:
        self.transaction_recovery_path.unlink(missing_ok=True)
        self._sync_root_directory()

    def _initialize_database(self) -> None:
        with self._exclusive_blob_lock(), self.connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_uri TEXT PRIMARY KEY,
                    manifest_digest TEXT NOT NULL UNIQUE,
                    object_digest TEXT NOT NULL,
                    payload_digest TEXT NOT NULL,
                    schema_uri TEXT NOT NULL,
                    semantics_uri TEXT NOT NULL,
                    canonicalizer_digest TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    committed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS artifacts_object_digest
                    ON artifacts(object_digest);
                CREATE TABLE IF NOT EXISTS artifact_parents (
                    artifact_uri TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    parent_uri TEXT NOT NULL,
                    PRIMARY KEY (artifact_uri, position),
                    FOREIGN KEY (artifact_uri)
                        REFERENCES artifacts(artifact_uri)
                        ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS blob_quota (
                    id INTEGER PRIMARY KEY CHECK (id = 0),
                    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
                    reconciliation_required INTEGER NOT NULL DEFAULT 1
                        CHECK (reconciliation_required IN (0, 1))
                );
                """
            )
            quota_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(blob_quota)")
            }
            if "reconciliation_required" not in quota_columns:
                connection.execute(
                    """
                    ALTER TABLE blob_quota
                    ADD COLUMN reconciliation_required
                        INTEGER NOT NULL DEFAULT 1
                        CHECK (reconciliation_required IN (0, 1))
                    """
                )
        self._reconcile_blob_quota()

    def _blob_path(self, digest: str) -> Path:
        hex_digest = digest.removeprefix("sha256:")
        if len(hex_digest) != 64 or any(
            char not in "0123456789abcdef"  # pragma: allowlist secret
            for char in hex_digest
        ):
            raise ArtifactIntegrityError(f"invalid blob digest: {digest!r}")
        return self.blob_root / hex_digest[:2] / hex_digest[2:]

    def _scan_blob_bytes_committed(self) -> tuple[int, set[Path]]:
        total = 0
        observed_prefixes: set[Path] = set()
        for prefix in self.blob_root.iterdir():
            if not prefix.is_dir() or prefix.is_symlink():
                continue
            observed_prefixes.add(prefix)
            for blob in prefix.iterdir():
                if blob.is_file() and not blob.is_symlink():
                    digest = f"sha256:{prefix.name}{blob.name}"
                    before = blob.stat()
                    data = blob.read_bytes()
                    after = blob.stat()
                    before_signature = (
                        before.st_dev,
                        before.st_ino,
                        before.st_size,
                        before.st_mtime_ns,
                        before.st_ctime_ns,
                    )
                    after_signature = (
                        after.st_dev,
                        after.st_ino,
                        after.st_size,
                        after.st_mtime_ns,
                        after.st_ctime_ns,
                    )
                    if before_signature != after_signature:
                        raise ArtifactIntegrityError(
                            f"blob changed during store recovery: {digest}"
                        )
                    if _sha256(data) != digest:
                        raise ArtifactIntegrityError(
                            f"blob digest mismatch during store recovery: {digest}"
                        )
                    self._validated_blobs[digest] = after_signature
                    total += after.st_size
        return total, observed_prefixes

    def _reconcile_blob_quota(self, *, force: bool = False) -> None:
        """Recover quota accounting only after an interrupted blob mutation."""

        with self._exclusive_blob_lock():
            force = force or self.transaction_recovery_path.exists()
            with self.connection() as connection:
                row = connection.execute(
                    """
                    SELECT reconciliation_required
                    FROM blob_quota
                    WHERE id = 0
                    """
                ).fetchone()
                if force:
                    connection.execute(
                        """
                        UPDATE blob_quota
                        SET reconciliation_required = 1
                        WHERE id = 0
                        """
                    )
            if (
                os.name != "nt"
                and not force
                and row is not None
                and not bool(row["reconciliation_required"])
            ):
                return

            total, observed_prefixes = self._scan_blob_bytes_committed()
            for prefix in sorted(observed_prefixes, key=str):
                self._sync_directory(prefix)
            self._sync_directory(self.blob_root)
            with self.connection() as connection:
                connection.execute(
                    """
                    INSERT INTO blob_quota (
                        id,
                        size_bytes,
                        reconciliation_required
                    )
                    VALUES (0, ?, 0)
                    ON CONFLICT(id) DO UPDATE
                    SET size_bytes = excluded.size_bytes,
                        reconciliation_required = 0
                    """,
                    (total,),
                )
            if self.transaction_recovery_path.exists():
                self._remove_transaction_recovery_marker()

    def _blob_bytes_committed(self) -> int:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT size_bytes, reconciliation_required
                FROM blob_quota
                WHERE id = 0
                """
            ).fetchone()
        if row is None:
            raise ArtifactIntegrityError("artifact store quota metadata is missing")
        if bool(row["reconciliation_required"]):
            raise ArtifactIntegrityError(
                "artifact store quota metadata requires recovery"
            )
        return int(row["size_bytes"])

    def _adjust_blob_bytes_committed(
        self,
        delta: int,
        *,
        reconciliation_required: bool,
    ) -> None:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE blob_quota
                SET size_bytes = size_bytes + ?,
                    reconciliation_required = ?
                WHERE id = 0 AND size_bytes + ? >= 0
                """,
                (delta, int(reconciliation_required), delta),
            )
        if cursor.rowcount != 1:
            raise ArtifactIntegrityError("artifact store quota metadata is invalid")

    def _mark_blob_quota_reconciled(self) -> None:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE blob_quota
                SET reconciliation_required = 0
                WHERE id = 0
                """
            )
        if cursor.rowcount != 1:
            raise ArtifactIntegrityError("artifact store quota metadata is missing")

    @contextmanager
    def _exclusive_blob_lock(self) -> Iterator[None]:
        """Serialize quota accounting and blob publication across processes."""

        if self._connection_state.blob_lock_depth:
            self._connection_state.blob_lock_depth += 1
            try:
                yield
            finally:
                self._connection_state.blob_lock_depth -= 1
            return

        with self.blob_lock_path.open("a+b") as lock_file:
            _lock_file(lock_file)
            self._connection_state.blob_lock_depth = 1
            try:
                yield
            finally:
                self._connection_state.blob_lock_depth = 0
                _unlock_file(lock_file)

    def _write_blob(self, data: bytes) -> str:
        try:
            return self._write_blob_unchecked(data)
        except (OSError, sqlite3.Error) as exc:
            _LOGGER.exception("filesystem error while writing artifact data")
            raise StoreError(
                "Jacobian could not write artifact data. Check the state directory "
                "and available disk space, then retry."
            ) from exc

    def _write_blob_unchecked(self, data: bytes) -> str:
        digest = _sha256(data)
        target = self._blob_path(digest)
        with self._exclusive_blob_lock():
            if not self.transaction_active and self.transaction_recovery_path.exists():
                self._reconcile_blob_quota(force=True)
            prefix_created = not target.parent.exists()
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.parent.is_symlink() or not target.parent.is_dir():
                raise ArtifactIntegrityError(
                    f"blob prefix is not a local directory for {digest}"
                )
            if target.exists():
                if target.is_symlink() or not target.is_file():
                    raise ArtifactIntegrityError(
                        f"existing blob does not match digest {digest}"
                    )
                stat = target.stat()
                signature = (
                    stat.st_dev,
                    stat.st_ino,
                    stat.st_size,
                    stat.st_mtime_ns,
                    stat.st_ctime_ns,
                )
                if self._validated_blobs.get(digest) == signature:
                    return digest
                existing = target.read_bytes()
                after = target.stat()
                after_signature = (
                    after.st_dev,
                    after.st_ino,
                    after.st_size,
                    after.st_mtime_ns,
                    after.st_ctime_ns,
                )
                if signature != after_signature or existing != data:
                    raise ArtifactIntegrityError(
                        f"existing blob does not match digest {digest}"
                    )
                self._validated_blobs[digest] = after_signature
                return digest
            if (
                self._blob_bytes_committed() + len(data)
                > self.limits.max_total_blob_bytes
            ):
                raise StoreLimitError("artifact store blob quota would be exceeded")

            descriptor, temporary_name = tempfile.mkstemp(
                dir=self.staging_root,
                prefix="blob-",
            )
            temporary = Path(temporary_name)
            reserved = False
            published = False
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                self._adjust_blob_bytes_committed(
                    len(data),
                    reconciliation_required=True,
                )
                reserved = True
                try:
                    os.link(temporary, target)
                    published = True
                except FileExistsError as exc:
                    if target.is_symlink() or target.read_bytes() != data:
                        raise ArtifactIntegrityError(
                            f"concurrent blob does not match digest {digest}"
                        ) from exc
                self._sync_blob_publication_directories(
                    target.parent,
                    prefix_created=prefix_created,
                )
            finally:
                temporary.unlink(missing_ok=True)
                if reserved and not published:
                    try:
                        self._adjust_blob_bytes_committed(
                            -len(data),
                            reconciliation_required=False,
                        )
                    except (ArtifactIntegrityError, sqlite3.Error):
                        _LOGGER.exception(
                            "failed to release an unpublished blob quota reservation"
                        )
            if published:
                self._mark_blob_quota_reconciled()
            stat = target.stat()
            self._validated_blobs[digest] = (
                stat.st_dev,
                stat.st_ino,
                stat.st_size,
                stat.st_mtime_ns,
                stat.st_ctime_ns,
            )
        return digest

    def _artifact_exists(self, artifact_uri: str) -> bool:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM artifacts WHERE artifact_uri = ?",
                (artifact_uri,),
            ).fetchone()
        return row is not None

    def register_descriptor(
        self,
        *,
        kind: str,
        name: str,
        version: str,
        definition: Any,
    ) -> str:
        """Register an operator-owned infrastructure descriptor."""

        if kind not in {
            "schema",
            "semantics",
            "canonicalizer",
            "implementation",
        }:
            raise ValueError(f"unsupported descriptor kind: {kind!r}")
        result = self._put(
            schema_uri=_BOOTSTRAP_SCHEMA_URI,
            semantics_uri=_BOOTSTRAP_SEMANTICS_URI,
            payload={
                "descriptor_version": "1",
                "kind": kind,
                "name": name,
                "version": version,
                "definition": definition,
            },
            parents=(),
            summary=f"{kind}: {name}@{version}",
            allow_bootstrap_references=True,
        )
        return result.artifact_uri

    def get_descriptor(
        self,
        artifact_uri: str,
        *,
        expected_kind: str | None = None,
    ) -> dict[str, Any]:
        """Load an infrastructure descriptor and optionally require its kind."""

        artifact = self.get(artifact_uri)
        if (
            artifact.manifest.schema_uri != _BOOTSTRAP_SCHEMA_URI
            or artifact.manifest.semantics_uri != _BOOTSTRAP_SEMANTICS_URI
            or not isinstance(artifact.payload, dict)
            or artifact.payload.get("descriptor_version") != "1"
        ):
            raise StoreError(f"artifact is not a system descriptor: {artifact_uri}")
        kind = artifact.payload.get("kind")
        if expected_kind is not None and kind != expected_kind:
            raise StoreError(
                f"descriptor kind {kind!r} does not match {expected_kind!r}"
            )
        return artifact.payload

    def put(
        self,
        *,
        schema_uri: str,
        semantics_uri: str,
        payload: Any,
        parents: tuple[str, ...] | list[str] = (),
        summary: str = "",
    ) -> ArtifactPutResult:
        """Commit canonical content whose identity binds schema and semantics."""

        return self._put(
            schema_uri=schema_uri,
            semantics_uri=semantics_uri,
            payload=payload,
            parents=tuple(parents),
            summary=summary,
            allow_bootstrap_references=False,
        )

    def _put(
        self,
        *,
        schema_uri: str,
        semantics_uri: str,
        payload: Any,
        parents: tuple[str, ...],
        summary: str,
        allow_bootstrap_references: bool,
    ) -> ArtifactPutResult:
        if len(summary) > self.limits.max_summary_chars:
            raise StoreLimitError("artifact summary exceeds the configured limit")
        if len(parents) > self.limits.max_parents:
            raise StoreLimitError("artifact parent count exceeds the configured limit")
        if len(set(parents)) != len(parents):
            raise StoreError("artifact parents must be unique")
        if not allow_bootstrap_references:
            for reference in (schema_uri, semantics_uri, *parents):
                _digest_from_uri(reference)
                if not self._artifact_exists(reference):
                    raise ArtifactNotFoundError(
                        f"referenced artifact is not committed: {reference}"
                    )

        canonical_bytes = canonicalize_json(payload, limits=self.canonical_limits)
        if len(canonical_bytes) > self.limits.max_artifact_bytes:
            raise StoreLimitError("artifact exceeds the configured size limit")

        object_digest = _framed_digest(
            _OBJECT_FORMAT_VERSION,
            (
                schema_uri.encode(),
                semantics_uri.encode(),
                CANONICALIZER_DIGEST.encode(),
                canonical_bytes,
            ),
        )
        payload_digest = _sha256(canonical_bytes)
        normalized_parents = tuple(sorted(parents))
        manifest = ArtifactManifest(
            object_digest=object_digest,
            payload_digest=payload_digest,
            schema_uri=schema_uri,
            semantics_uri=semantics_uri,
            canonicalizer_digest=CANONICALIZER_DIGEST,
            parents=normalized_parents,
            summary=summary,
        )
        manifest_bytes = canonicalize_json(
            manifest.model_dump(mode="json"),
            limits=self.canonical_limits,
        )
        manifest_digest = _sha256(manifest_bytes)
        artifact_uri = _uri_from_digest(manifest_digest)

        # Re-registering identical content is common while assembling built-in
        # portfolios. Validate the committed artifact before returning so the
        # idempotent path avoids both blob publication and metadata writes
        # without allowing missing or corrupted content to be silently healed.
        if self._artifact_exists(artifact_uri):
            self.get(artifact_uri)
            return ArtifactPutResult(
                artifact_uri=artifact_uri,
                object_digest=object_digest,
                manifest_digest=manifest_digest,
                canonicalizer_digest=CANONICALIZER_DIGEST,
            )

        self._write_blob(canonical_bytes)
        self._write_blob(manifest_bytes)

        with self.connection() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO artifacts (
                    artifact_uri,
                    manifest_digest,
                    object_digest,
                    payload_digest,
                    schema_uri,
                    semantics_uri,
                    canonicalizer_digest,
                    summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_uri,
                    manifest_digest,
                    object_digest,
                    payload_digest,
                    schema_uri,
                    semantics_uri,
                    CANONICALIZER_DIGEST,
                    summary,
                ),
            )
            for position, parent_uri in enumerate(normalized_parents):
                connection.execute(
                    """
                    INSERT OR IGNORE INTO artifact_parents (
                        artifact_uri, position, parent_uri
                    ) VALUES (?, ?, ?)
                    """,
                    (artifact_uri, position, parent_uri),
                )

        return ArtifactPutResult(
            artifact_uri=artifact_uri,
            object_digest=object_digest,
            manifest_digest=manifest_digest,
            canonicalizer_digest=CANONICALIZER_DIGEST,
        )

    def _read_blob(self, digest: str) -> bytes:
        path = self._blob_path(digest)
        if not path.exists():
            raise ArtifactNotFoundError(f"missing blob for digest {digest}")
        if path.is_symlink() or not path.is_file():
            raise ArtifactIntegrityError(f"blob path is not a regular file: {digest}")
        data = path.read_bytes()
        if _sha256(data) != digest:
            raise ArtifactIntegrityError(f"blob digest mismatch: {digest}")
        return data

    def get(self, artifact_uri: str) -> StoredArtifact:
        """Load an artifact after replaying its content and manifest digests."""

        manifest_digest = _digest_from_uri(artifact_uri)
        committed_references: set[str] = set()
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM artifacts WHERE artifact_uri = ?",
                (artifact_uri,),
            ).fetchone()
            parent_rows = connection.execute(
                """
                SELECT
                    parent.parent_uri,
                    committed.artifact_uri AS committed_parent_uri
                FROM artifact_parents AS parent
                LEFT JOIN artifacts AS committed
                    ON committed.artifact_uri = parent.parent_uri
                WHERE parent.artifact_uri = ?
                ORDER BY parent.position
                """,
                (artifact_uri,),
            ).fetchall()
            if row is not None:
                committed_references = {
                    str(reference["artifact_uri"])
                    for reference in connection.execute(
                        """
                        SELECT artifact_uri
                        FROM artifacts
                        WHERE artifact_uri IN (?, ?)
                        """,
                        (row["schema_uri"], row["semantics_uri"]),
                    ).fetchall()
                }
        if row is None:
            raise ArtifactNotFoundError(f"artifact is not committed: {artifact_uri}")

        manifest_bytes = self._read_blob(manifest_digest)
        manifest_data = loads_strict_json(
            manifest_bytes,
            limits=self.canonical_limits,
        )
        manifest = ArtifactManifest.model_validate(manifest_data)
        database_parents = tuple(parent["parent_uri"] for parent in parent_rows)
        if any(parent["committed_parent_uri"] is None for parent in parent_rows):
            raise ArtifactIntegrityError("manifest parent is not committed")
        if manifest.parents != database_parents:
            raise ArtifactIntegrityError("manifest parents differ from metadata")
        if (
            manifest_digest != row["manifest_digest"]
            or manifest.object_digest != row["object_digest"]
            or manifest.payload_digest != row["payload_digest"]
            or manifest.schema_uri != row["schema_uri"]
            or manifest.semantics_uri != row["semantics_uri"]
            or manifest.canonicalizer_digest != row["canonicalizer_digest"]
            or manifest.summary != row["summary"]
        ):
            raise ArtifactIntegrityError("manifest differs from committed metadata")
        if (
            manifest.schema_uri,
            manifest.semantics_uri,
        ) != (_BOOTSTRAP_SCHEMA_URI, _BOOTSTRAP_SEMANTICS_URI) and {
            manifest.schema_uri,
            manifest.semantics_uri,
        } != committed_references:
            raise ArtifactIntegrityError(
                "manifest schema or semantics is not committed"
            )

        canonical_bytes = self._read_blob(manifest.payload_digest)
        recomputed_object_digest = _framed_digest(
            _OBJECT_FORMAT_VERSION,
            (
                manifest.schema_uri.encode(),
                manifest.semantics_uri.encode(),
                manifest.canonicalizer_digest.encode(),
                canonical_bytes,
            ),
        )
        if recomputed_object_digest != manifest.object_digest:
            raise ArtifactIntegrityError("mathematical object digest mismatch")
        payload = loads_strict_json(canonical_bytes, limits=self.canonical_limits)
        return StoredArtifact(
            artifact_uri=artifact_uri,
            manifest=manifest,
            payload=payload,
            canonical_bytes=canonical_bytes,
        )

    def find_by_object_digest(self, object_digest: str) -> tuple[str, ...]:
        """Return every artifact URI carrying a mathematical object digest."""

        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT artifact_uri
                FROM artifacts
                WHERE object_digest = ?
                ORDER BY artifact_uri
                """,
                (object_digest,),
            ).fetchall()
        return tuple(row["artifact_uri"] for row in rows)
