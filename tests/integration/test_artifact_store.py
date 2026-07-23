from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest

from jacobian.canonical import CanonicalizationError
from jacobian.store import (
    ArtifactIntegrityError,
    ArtifactStore,
    StoreLimitError,
    StoreLimits,
)


@pytest.mark.integration
@pytest.mark.conformance
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


@pytest.mark.integration
@pytest.mark.conformance
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


@pytest.mark.integration
@pytest.mark.conformance
def test_over_limit_artifact_leaves_no_partial_metadata(tmp_path: Path) -> None:
    store = ArtifactStore(
        tmp_path,
        limits=StoreLimits(
            max_artifact_bytes=2048,
            max_total_blob_bytes=1024 * 1024,
        ),
    )
    schema = store.register_descriptor(
        kind="schema",
        name="bounded.candidate",
        version="1",
        definition={"type": "object"},
    )
    semantics = store.register_descriptor(
        kind="semantics",
        name="bounded.candidate",
        version="1",
        definition={"description": "bounded fixture"},
    )
    blobs_before = {
        path.relative_to(tmp_path)
        for path in (tmp_path / "blobs" / "sha256").glob("*/*")
    }

    with pytest.raises(CanonicalizationError, match="size limit"):
        store.put(
            schema_uri=schema,
            semantics_uri=semantics,
            payload={"value": "x" * 4096},
        )

    blobs_after = {
        path.relative_to(tmp_path)
        for path in (tmp_path / "blobs" / "sha256").glob("*/*")
    }
    assert blobs_after == blobs_before


@pytest.mark.integration
@pytest.mark.conformance
def test_concurrent_blob_commits_cannot_oversubscribe_quota(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ArtifactStore(
        tmp_path,
        limits=StoreLimits(
            max_artifact_bytes=2048,
            max_total_blob_bytes=900,
        ),
    )
    first_accounting = threading.Event()
    release_first = threading.Event()
    call_lock = threading.Lock()
    accounting_calls = 0
    original_accounting = store._blob_bytes_committed

    def paused_accounting() -> int:
        nonlocal accounting_calls
        with call_lock:
            accounting_calls += 1
            call_number = accounting_calls
        if call_number == 1:
            first_accounting.set()
            assert release_first.wait(timeout=2)
        return original_accounting()

    monkeypatch.setattr(store, "_blob_bytes_committed", paused_accounting)
    outcomes: list[Any] = []

    def commit(data: bytes) -> None:
        try:
            outcomes.append(store._write_blob(data))
        except Exception as exc:
            outcomes.append(exc)

    first = threading.Thread(target=commit, args=(b"a" * 600,))
    second = threading.Thread(target=commit, args=(b"b" * 600,))
    first.start()
    assert first_accounting.wait(timeout=1)
    second.start()
    time.sleep(0.1)

    with call_lock:
        assert accounting_calls == 1

    release_first.set()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert sum(isinstance(outcome, str) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, StoreLimitError) for outcome in outcomes) == 1
