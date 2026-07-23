"""Application composition root for the v0.1 research kernel."""

from __future__ import annotations

from pathlib import Path

from jacobian.artifacts import ArtifactService
from jacobian.claims import ClaimValidationService
from jacobian.evaluation import EvaluationService
from jacobian.plugin_execution import PluginExecutor
from jacobian.plugins.registry import PluginRegistry
from jacobian.references import (
    ReferenceInstallation,
    ReferenceInstaller,
)
from jacobian.registry import CheckerRegistry
from jacobian.schema_registry import SchemaRegistry
from jacobian.shrinking import ShrinkService
from jacobian.store import ArtifactStore
from jacobian.verification import VerificationService
from jacobian.witnesses import WitnessSearchService


class JacobianKernel:
    """Local sequential v0.1 services over one content-addressed store."""

    def __init__(
        self,
        root: str | Path,
        *,
        install_references: bool = False,
    ) -> None:
        self.store = ArtifactStore(root)
        self.schemas = SchemaRegistry(self.store)
        self.artifacts = ArtifactService(self.store, self.schemas)
        self.plugins = PluginRegistry(self.store)
        self.checkers = CheckerRegistry(self.store.db_path)
        self.claims = ClaimValidationService(
            self.store,
            self.schemas,
            self.plugins,
        )
        self.plugin_executor = PluginExecutor()
        self.evaluation = EvaluationService(
            self.store,
            self.schemas,
            self.plugins,
            self.claims,
            self.plugin_executor,
        )
        self.verification = VerificationService(
            self.store,
            self.checkers,
        )
        self.witnesses = WitnessSearchService(
            self.store,
            self.schemas,
            self.plugins,
            self.claims,
            self.plugin_executor,
            self.verification,
        )
        self.shrinking = ShrinkService(
            self.store,
            self.schemas,
            self.plugins,
            self.claims,
            self.plugin_executor,
            self.verification,
        )
        self.reference_installer = ReferenceInstaller(
            self.store,
            self.schemas,
            self.artifacts,
            self.plugins,
            self.checkers,
        )
        self.references: dict[str, ReferenceInstallation] = {}
        if install_references:
            self.references = self.reference_installer.install_all()
