"""Narrow foundational dependencies shared by capability installers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from jacobian.artifacts import ArtifactService
from jacobian.capabilities import CapabilityAdapter, CapabilityService
from jacobian.operation_installation import OperationInstaller
from jacobian.registry import CheckerRegistry
from jacobian.runtime.config import CheckerAuthorityMode
from jacobian.schema_registry import SchemaRegistry
from jacobian.store import ArtifactStore
from jacobian.verification import VerificationService


@dataclass(frozen=True, slots=True)
class InstallationContext:
    """Infrastructure used across independent domain installers."""

    store: ArtifactStore
    schemas: SchemaRegistry
    artifacts: ArtifactService
    capabilities: CapabilityService
    checkers: CheckerRegistry
    verification: VerificationService
    operations: OperationInstaller
    checker_authority: CheckerAuthorityMode
    register_capability: Callable[[CapabilityAdapter], None]

    @property
    def authorizes_bundled_checkers(self) -> bool:
        """Whether built-in checker declarations may be authorized."""

        return self.checker_authority is CheckerAuthorityMode.INSTALL_BUNDLED
