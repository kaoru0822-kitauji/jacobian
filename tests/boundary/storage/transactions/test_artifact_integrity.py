from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from jacobian.canonical import CanonicalizationError
from jacobian.store import ArtifactIntegrityError, ArtifactStore, StoreError

def test_artifact_identity_uses_canonical_payload_schema_and_semantics(
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path)
    schema_a = store.register_descriptor(
        kind="schema",
        name="example.candidate",
        version="1",
        definition={"type": "object"},
    )
    schema_b = store.register_descriptor(
        kind="schema",
        name="example.candidate.alternate",
        version="1",
        definition={"type": "object"},
    )
    semantics_a = store.register_descriptor(
        kind="semantics",
        name="example.meaning",
        version="1",
        definition={"description": "first meaning"},
    )
    semantics_b = store.register_descriptor(
        kind="semantics",
        name="example.meaning.alternate",
        version="1",
        definition={"description": "second meaning"},
    )

    first = store.put(
        schema_uri=schema_a,
        semantics_uri=semantics_a,
        payload={"weight": {"num": "2", "den": "4"}},
        summary="candidate",
    )
    equivalent = store.put(
        schema_uri=schema_a,
        semantics_uri=semantics_a,
        payload={"weight": {"num": "1", "den": "2"}},
        summary="candidate",
    )
    different_schema = store.put(
        schema_uri=schema_b,
        semantics_uri=semantics_a,
        payload={"weight": {"num": "1", "den": "2"}},
        summary="candidate",
    )
    different_semantics = store.put(
        schema_uri=schema_a,
        semantics_uri=semantics_b,
        payload={"weight": {"num": "1", "den": "2"}},
        summary="candidate",
    )

    assert first == equivalent
    assert (
        len(
            {
                first.object_digest,
                different_schema.object_digest,
                different_semantics.object_digest,
            }
        )
        == 3
    )
    assert store.get(first.artifact_uri).payload == {"weight": {"den": "2", "num": "1"}}

def test_repeated_put_validates_without_blob_or_metadata_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ArtifactStore(tmp_path)
    schema = store.register_descriptor(
        kind="schema",
        name="example.candidate",
        version="1",
        definition={"type": "object"},
    )
    semantics = store.register_descriptor(
        kind="semantics",
        name="example.meaning",
        version="1",
        definition={"description": "meaning"},
    )
    expected = store.put(
        schema_uri=schema,
        semantics_uri=semantics,
        payload={"value": "unchanged"},
        summary="candidate",
    )

    original_connect = store._connect

    def connect_read_only() -> sqlite3.Connection:
        connection = original_connect()

        def deny_metadata_writes(
            action: int,
            _argument_one: str | None,
            _argument_two: str | None,
            _database: str | None,
            _trigger: str | None,
        ) -> int:
            if action in {
                sqlite3.SQLITE_DELETE,
                sqlite3.SQLITE_INSERT,
                sqlite3.SQLITE_UPDATE,
            }:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        connection.set_authorizer(deny_metadata_writes)
        return connection

    monkeypatch.setattr(store, "_connect", connect_read_only)

    def reject_blob_write(_data: bytes) -> str:
        pytest.fail("an idempotent put must not publish blobs")

    monkeypatch.setattr(store, "_write_blob", reject_blob_write)

    repeated = store.put(
        schema_uri=schema,
        semantics_uri=semantics,
        payload={"value": "unchanged"},
        summary="candidate",
    )

    assert repeated == expected

def test_repeated_put_rejects_corrupted_committed_blob(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    schema = store.register_descriptor(
        kind="schema",
        name="example.candidate",
        version="1",
        definition={"type": "object"},
    )
    semantics = store.register_descriptor(
        kind="semantics",
        name="example.meaning",
        version="1",
        definition={"description": "meaning"},
    )
    store.put(
        schema_uri=schema,
        semantics_uri=semantics,
        payload={"value": "original"},
    )
    payload_path = next(
        path
        for path in (tmp_path / "blobs" / "sha256").glob("*/*")
        if path.read_bytes() == b'{"value":"original"}'
    )
    payload_path.write_bytes(b'{"value":"tampered"}')

    with pytest.raises(ArtifactIntegrityError, match="blob digest mismatch"):
        store.put(
            schema_uri=schema,
            semantics_uri=semantics,
            payload={"value": "original"},
        )

def test_modified_blob_is_rejected_on_read(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    schema = store.register_descriptor(
        kind="schema",
        name="example.candidate",
        version="1",
        definition={"type": "object"},
    )
    semantics = store.register_descriptor(
        kind="semantics",
        name="example.meaning",
        version="1",
        definition={"description": "meaning"},
    )
    artifact = store.put(
        schema_uri=schema,
        semantics_uri=semantics,
        payload={"value": "original"},
    )

    payload_blob = next(
        path
        for path in (tmp_path / "blobs" / "sha256").glob("*/*")
        if path.read_bytes() == b'{"value":"original"}'
    )
    payload_blob.write_bytes(b'{"value":"tampered"}')

    with pytest.raises(ArtifactIntegrityError):
        store.get(artifact.artifact_uri)

@pytest.mark.parametrize("column", ["manifest_digest", "summary"])
def test_modified_artifact_metadata_is_rejected_on_read(
    tmp_path: Path,
    column: str,
) -> None:
    store = ArtifactStore(tmp_path)
    schema = store.register_descriptor(
        kind="schema",
        name="example.candidate",
        version="1",
        definition={"type": "object"},
    )
    semantics = store.register_descriptor(
        kind="semantics",
        name="example.meaning",
        version="1",
        definition={"description": "meaning"},
    )
    artifact = store.put(
        schema_uri=schema,
        semantics_uri=semantics,
        payload={"value": "original"},
        summary="original summary",
    )

    replacement = (
        "sha256:" + "0" * 64 if column == "manifest_digest" else "tampered summary"
    )
    with sqlite3.connect(store.db_path) as connection:
        if column == "manifest_digest":
            connection.execute(
                """
                UPDATE artifacts
                SET manifest_digest = ?
                WHERE artifact_uri = ?
                """,
                (replacement, artifact.artifact_uri),
            )
        else:
            connection.execute(
                """
                UPDATE artifacts
                SET summary = ?
                WHERE artifact_uri = ?
                """,
                (replacement, artifact.artifact_uri),
            )

    with pytest.raises(ArtifactIntegrityError, match="manifest differs"):
        store.get(artifact.artifact_uri)

@pytest.mark.parametrize("missing_reference", ["parent", "schema", "semantics"])
def test_missing_reference_metadata_is_rejected_on_read(
    tmp_path: Path,
    missing_reference: str,
) -> None:
    store = ArtifactStore(tmp_path)
    schema = store.register_descriptor(
        kind="schema",
        name="example.candidate",
        version="1",
        definition={"type": "object"},
    )
    semantics = store.register_descriptor(
        kind="semantics",
        name="example.meaning",
        version="1",
        definition={"description": "meaning"},
    )
    parent = store.put(
        schema_uri=schema,
        semantics_uri=semantics,
        payload={"kind": "parent"},
    )
    child = store.put(
        schema_uri=schema,
        semantics_uri=semantics,
        payload={"kind": "child"},
        parents=(parent.artifact_uri,),
    )

    deleted_uri = {
        "parent": parent.artifact_uri,
        "schema": schema,
        "semantics": semantics,
    }[missing_reference]
    with sqlite3.connect(store.db_path) as connection:
        connection.execute(
            "DELETE FROM artifacts WHERE artifact_uri = ?",
            (deleted_uri,),
        )

    with pytest.raises(ArtifactIntegrityError, match="is not committed"):
        store.get(child.artifact_uri)

def test_duplicate_put_rechecks_a_changed_blob(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    original = b"original"
    digest = store._write_blob(original)
    store._blob_path(digest).write_bytes(b"tampered")

    with pytest.raises(ArtifactIntegrityError, match="does not match"):
        store._write_blob(original)

def test_store_keeps_filesystem_paths_local(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = ArtifactStore(tmp_path)
    schema = store.register_descriptor(
        kind="schema",
        name="example.candidate",
        version="1",
        definition={"type": "object"},
    )
    semantics = store.register_descriptor(
        kind="semantics",
        name="example.meaning",
        version="1",
        definition={"description": "meaning"},
    )
    original_mkdir = Path.mkdir

    def fail_blob_directory(
        path: Path,
        mode: int = 0o777,
        parents: bool = False,
        exist_ok: bool = False,
    ) -> None:
        if store.blob_root in path.parents:
            raise OSError("simulated filesystem failure at /private/provider/blob/path")
        original_mkdir(
            path,
            mode=mode,
            parents=parents,
            exist_ok=exist_ok,
        )

    monkeypatch.setattr(Path, "mkdir", fail_blob_directory)

    with pytest.raises(
        StoreError,
        match=(
            r"Jacobian could not write artifact data\. Check the state directory "
            r"and available disk space, then retry\."
        ),
    ) as raised:
        store.put(
            schema_uri=schema,
            semantics_uri=semantics,
            payload={"unique": "filesystem-error"},
        )
    assert "/private/provider" not in str(raised.value)
    assert "/private/provider" in caplog.text
