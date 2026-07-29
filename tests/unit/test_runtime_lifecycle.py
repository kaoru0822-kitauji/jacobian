"""Behavioral audit of :class:`JacobianRuntime` lifecycle ownership.

These tests pin the runtime ownership contract: explicit ``close``,
idempotence, context-manager semantics, partial-bootstrap failure cleanup,
and use-after-close behavior. The runtime delegates storage ownership to
:class:`ArtifactStore`; these tests verify that delegation closes the store
and that construction failures release every owned resource.

The contract is verified through observable use-after-close behavior rather
than private ``_closed`` flags wherever possible.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.runtime import create_runtime
from jacobian.runtime.model import RuntimeClosedError
from jacobian.store import StoreClosedError


def test_close_is_idempotent(tmp_path: Path) -> None:
    runtime = create_runtime(tmp_path)

    runtime.close()
    runtime.close()
    with pytest.raises(StoreClosedError):
        runtime.core.store.register_descriptor(
            kind="schema",
            name="after-double-close",
            version="1",
            definition={"type": "object"},
        )
    with pytest.raises(RuntimeClosedError), runtime:
        pytest.fail("entering a closed runtime must not succeed")


def test_context_manager_closes_runtime(tmp_path: Path) -> None:
    with create_runtime(tmp_path) as runtime:
        # While open the store is usable.
        runtime.core.store.register_descriptor(
            kind="schema",
            name="example.in-context",
            version="1",
            definition={"type": "object"},
        )
    # After the context manager exits the store is closed.
    with pytest.raises(StoreClosedError):
        runtime.core.store.register_descriptor(
            kind="schema",
            name="after-context",
            version="1",
            definition={"type": "object"},
        )


def test_context_manager_exit_suppresses_no_exception(tmp_path: Path) -> None:
    runtime = create_runtime(tmp_path)
    with pytest.raises(ValueError, match="body failure"), runtime:
        raise ValueError("body failure")
    # The store is still closed even though the body raised.
    with pytest.raises(StoreClosedError):
        runtime.core.store.register_descriptor(
            kind="schema",
            name="after-body-failure",
            version="1",
            definition={"type": "object"},
        )


def test_partial_initialize_failure_releases_owned_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # If capability installation fails partway through construction, the
    # runtime must still release the store it already owns so that no SQLite
    # lifetime is leaked. The partially constructed runtime is unreachable
    # from the caller, so the proof is that the same root can be reopened
    # cleanly afterwards without a stale transaction-recovery marker.
    def boom(self: object, *args: object, **kwargs: object) -> None:
        raise RuntimeError("boom during initialize")

    monkeypatch.setattr("jacobian.portfolio.assembler.PortfolioAssembler.install", boom)

    with pytest.raises(RuntimeError, match="boom during initialize"):
        create_runtime(tmp_path)

    # Undo the failure injection so the reopened runtime can install its
    # portfolio normally.
    monkeypatch.undo()

    # The store must have been closed by the construction-failure cleanup, so a
    # fresh runtime can take ownership of the same root without conflict.
    reopened = create_runtime(tmp_path)
    try:
        reopened.core.store.register_descriptor(
            kind="schema",
            name="after-partial-initialize",
            version="1",
            definition={"type": "object"},
        )
    finally:
        reopened.close()


def test_partial_bootstrap_failure_releases_owned_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # If the foundational service bootstrap fails before the runtime is even
    # constructed, the store it opened must be closed by the bootstrap cleanup.
    def failing_install(*args: object, **kwargs: object) -> None:
        raise RuntimeError("bootstrap failure")

    monkeypatch.setattr(
        "jacobian.runtime.bootstrap.install_sat_artifacts",
        failing_install,
    )

    with pytest.raises(RuntimeError, match="bootstrap failure"):
        create_runtime(tmp_path)

    # A fresh store can reopen the same root cleanly afterwards.
    from jacobian.store import ArtifactStore

    reopened = ArtifactStore(tmp_path)
    reopened.close()


def test_close_failure_keeps_store_closable_on_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression test: JacobianRuntime.close() must set its closed marker only
    # after core.close() succeeds. If service close raises, the runtime
    # must remain closable so a retry can still release the underlying store.
    runtime = create_runtime(tmp_path)
    store = runtime.core.store

    def failing_close(self: object) -> None:
        raise RuntimeError("service close failed")

    monkeypatch.setattr(
        "jacobian.runtime.services.CoreServices.close",
        failing_close,
    )

    with pytest.raises(RuntimeError, match="service close failed"):
        runtime.close()

    # The store was not closed by the failed runtime close. Retrying the
    # runtime close (with the real service close restored) must eventually
    # release the store rather than returning early as already-closed.
    monkeypatch.undo()
    runtime.close()

    with pytest.raises(StoreClosedError), store.connection():
        pass
