"""Application composition root for the v0.2 research kernel."""

from __future__ import annotations

from pathlib import Path

from jacobian.artifacts import ArtifactService
from jacobian.claims import ClaimValidationService
from jacobian.conjectures import ConjectureService
from jacobian.contracts.lean import LeanEnvironment
from jacobian.evaluation import EvaluationService
from jacobian.experiments import ExperimentService
from jacobian.lean import LeanService
from jacobian.plugin_execution import PluginExecutor
from jacobian.plugins.registry import PluginRegistry
from jacobian.polytope import PolytopeService
from jacobian.references import (
    LeanCheckerInstallation,
    PolytopeCheckerInstallation,
    ReferenceInstallation,
    ReferenceInstaller,
)
from jacobian.registry import CheckerRegistry
from jacobian.schema_registry import SchemaRegistry
from jacobian.search import SearchService
from jacobian.shrinking import ShrinkService
from jacobian.store import ArtifactStore
from jacobian.structures import StructureService
from jacobian.transformations import TransformationService
from jacobian.verification import VerificationService
from jacobian.witnesses import WitnessSearchService
from jacobian.workflows import VerificationWorkflowService


class JacobianKernel:
    """Local v0.2 services over one content-addressed store."""

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
        self.structures = StructureService(
            self.store,
            self.schemas,
            self.plugins,
            self.plugin_executor,
        )
        self.transformations = TransformationService(
            self.store,
            self.schemas,
            self.plugins,
            self.plugin_executor,
        )
        self.polytope = PolytopeService(self.store, self.schemas)
        self.evaluation = EvaluationService(
            self.store,
            self.schemas,
            self.plugins,
            self.claims,
            self.plugin_executor,
        )
        self.experiments = ExperimentService(
            self.store,
            self.schemas,
            self.plugins,
            self.claims,
            self.plugin_executor,
            self.evaluation,
            self.structures,
        )
        self.verification = VerificationService(
            self.store,
            self.checkers,
            checker_timeout_seconds=75,
        )
        self.witnesses = WitnessSearchService(
            self.store,
            self.schemas,
            self.plugins,
            self.claims,
            self.plugin_executor,
            self.verification,
        )
        self.search = SearchService(
            self.store,
            self.schemas,
            self.plugins,
            self.claims,
            self.plugin_executor,
            self.evaluation,
            self.witnesses,
            self.verification,
        )
        self.conjectures = ConjectureService(
            self.store,
            self.schemas,
            self.plugins,
            self.claims,
            self.plugin_executor,
            self.search,
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
            transformation_claim_schema_uri=(self.transformations.claim_schema_uri),
        )
        self.references: dict[str, ReferenceInstallation] = {}
        self.polytope_checkers: PolytopeCheckerInstallation | None = None
        self.lean_checkers: dict[LeanEnvironment, LeanCheckerInstallation] = {}
        self.lean: LeanService | None = None
        self.verification_workflows: VerificationWorkflowService | None = None
        if install_references:
            self.references = self.reference_installer.install_all()
            self.polytope_checkers = self.reference_installer.install_polytope_checkers(
                claim_schema_uri=self.polytope.claim_schema_uri,
                semantics_uri=self.polytope.semantics_uri,
                point_schema_uri=self.polytope.point_schema_uri,
            )
            self.lean_checkers = self.reference_installer.install_lean_checkers()
            self.lean = LeanService(
                self.store,
                self.artifacts,
                self.verification,
                self.lean_checkers,
            )
            self.verification_workflows = VerificationWorkflowService(
                self.store,
                self.artifacts,
                self.claims,
                self.evaluation,
                self.witnesses,
                self.verification,
                self.references,
            )
