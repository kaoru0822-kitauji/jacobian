from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from jacobian.artifacts import ArtifactService
from jacobian.registry import CheckerRegistry
from jacobian.schema_registry import SchemaRegistry
from jacobian.store import ArtifactStore
from jacobian.verification import VerificationService


def install_capability_bundle(
    tmp_path: Path,
    installer: Callable[..., tuple[Any, Any]],
) -> tuple[Any, Any, ArtifactStore]:
    """Build a minimal store and install one capability bundle for focused tests."""

    store = ArtifactStore(tmp_path / "store")
    schemas = SchemaRegistry(store)
    artifacts = ArtifactService(store, schemas)
    checkers = CheckerRegistry(tmp_path / "checkers.sqlite3")
    verification = VerificationService(store, checkers)
    adapters, installed = installer(
        store,
        schemas,
        artifacts,
        verification,
        checkers,
        authorize_checker=True,
    )
    return adapters, installed, store
