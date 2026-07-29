"""Fixtures for component tests.

Component fixtures may open one real store/service graph, but never construct
the complete runtime or install the built-in portfolio.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from jacobian.runtime.services import CoreServices
from jacobian.store import ArtifactStore
from tests.support.services import open_core_services


@pytest.fixture
def artifact_store(tmp_path: Path) -> Iterator[ArtifactStore]:
    """Open one test-owned SQLite store for a storage-backed component."""

    store = ArtifactStore(tmp_path / "state")
    try:
        yield store
    finally:
        store.close()


@pytest.fixture
def core_services(tmp_path: Path) -> Iterator[CoreServices]:
    """Open foundational services without domain or portfolio installation."""

    with open_core_services(tmp_path / "state") as services:
        yield services
