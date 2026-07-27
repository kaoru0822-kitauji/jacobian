"""Atomic local content-addressed artifact storage."""

from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import tempfile
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
        self._validated_blobs: dict[str, tuple[int, int, int, int, int]] = {}
        self.blob_root.mkdir(parents=True, exist_ok=True)
        self.staging_root.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
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
                    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0)
                );
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

    def _scan_blob_bytes_committed(self) -> int:
        total = 0
        for prefix in self.blob_root.iterdir():
            if not prefix.is_dir() or prefix.is_symlink():
                continue
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
        return total

    def _reconcile_blob_quota(self) -> None:
        """Rebuild durable quota accounting once when the store is opened."""

        with self._exclusive_blob_lock():
            total = self._scan_blob_bytes_committed()
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO blob_quota (id, size_bytes)
                    VALUES (0, ?)
                    ON CONFLICT(id) DO UPDATE
                    SET size_bytes = excluded.size_bytes
                    """,
                    (total,),
                )

    def _blob_bytes_committed(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT size_bytes FROM blob_quota WHERE id = 0"
            ).fetchone()
        if row is None:
            raise ArtifactIntegrityError("artifact store quota metadata is missing")
        return int(row["size_bytes"])

    def _adjust_blob_bytes_committed(self, delta: int) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE blob_quota
                SET size_bytes = size_bytes + ?
                WHERE id = 0 AND size_bytes + ? >= 0
                """,
                (delta, delta),
            )
        if cursor.rowcount != 1:
            raise ArtifactIntegrityError("artifact store quota metadata is invalid")

    @contextmanager
    def _exclusive_blob_lock(self) -> Iterator[None]:
        """Serialize quota accounting and blob publication across processes."""

        with self.blob_lock_path.open("a+b") as lock_file:
            _lock_file(lock_file)
            try:
                yield
            finally:
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
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._exclusive_blob_lock():
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
                self._adjust_blob_bytes_committed(len(data))
                reserved = True
                try:
                    os.link(temporary, target)
                    published = True
                except FileExistsError as exc:
                    if target.is_symlink() or target.read_bytes() != data:
                        raise ArtifactIntegrityError(
                            f"concurrent blob does not match digest {digest}"
                        ) from exc
                if os.name != "nt":
                    directory_descriptor = os.open(target.parent, os.O_RDONLY)
                    try:
                        os.fsync(directory_descriptor)
                    finally:
                        os.close(directory_descriptor)
            finally:
                temporary.unlink(missing_ok=True)
                if reserved and not published:
                    try:
                        self._adjust_blob_bytes_committed(-len(data))
                    except (ArtifactIntegrityError, sqlite3.Error):
                        _LOGGER.exception(
                            "failed to release an unpublished blob quota reservation"
                        )
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
        with self._connect() as connection:
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
        self._write_blob(canonical_bytes)
        self._write_blob(manifest_bytes)

        with self._connect() as connection:
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
        with self._connect() as connection:
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

        with self._connect() as connection:
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
