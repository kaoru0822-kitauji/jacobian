"""Application composition root for the v0.2 research kernel."""

from __future__ import annotations

from pathlib import Path

from jacobian.artifacts import ArtifactService
from jacobian.atomic_capabilities import install_atomic_capabilities
from jacobian.builtin_capabilities import (
    KnowledgeSearchAdapter,
    LeanCheckAdapter,
)
from jacobian.capabilities import (
    CapabilityAdapter,
    CapabilityService,
    load_capability_adapter,
)
from jacobian.claims import ClaimValidationService
from jacobian.conjectures import ConjectureService
from jacobian.contracts.lean import LeanEnvironment
from jacobian.evaluation import EvaluationService
from jacobian.experiment_router import ExperimentRouter
from jacobian.experiments import ExperimentService
from jacobian.finite_partition import (
    FinitePartitionInstallation,
    install_finite_partition,
)
from jacobian.graph_capabilities import GraphInstallation, install_graph_capabilities
from jacobian.lean import LeanService
from jacobian.memory import ResearchMemory
from jacobian.plugin_execution import PluginExecutor
from jacobian.plugins.registry import PluginRegistry
from jacobian.polynomial_capabilities import (
    PolynomialInstallation,
    install_polynomial_capabilities,
)
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
from jacobian.universal_algebra_capabilities import (
    UniversalAlgebraInstallation,
    install_universal_algebra_capabilities,
)
from jacobian.verification import VerificationService
from jacobian.witnesses import WitnessSearchService


class JacobianKernel:
    """Local v0.2 services over one content-addressed store."""

    def __init__(
        self,
        root: str | Path,
        *,
        install_references: bool = False,
        capability_adapter_entrypoints: tuple[str, ...] = (),
    ) -> None:
        self.store = ArtifactStore(root)
        self.schemas = SchemaRegistry(self.store)
        self.artifacts = ArtifactService(self.store, self.schemas)
        self.memory = ResearchMemory(self.store, self.schemas)
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
            checker_timeout_seconds=105,
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
        self.experiment_router = ExperimentRouter(self.experiments, self.search)
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
        self.capabilities = CapabilityService(self.store, self.memory)
        for atomic_adapter in install_atomic_capabilities(self):
            self.capabilities.register(atomic_adapter)
        self.capabilities.register(KnowledgeSearchAdapter(self.memory))
        self.finite_partition: FinitePartitionInstallation
        finite_partition, self.finite_partition = install_finite_partition(
            self.store,
            self.schemas,
            self.artifacts,
            self.verification,
            self.checkers,
            authorize_checker=install_references,
        )
        self.capabilities.register(finite_partition)
        self.graph: GraphInstallation
        graph_adapters, self.graph = install_graph_capabilities(
            self.store,
            self.schemas,
            self.artifacts,
            self.checkers,
            authorize_checker=install_references,
        )
        for graph_adapter in graph_adapters:
            self.capabilities.register(graph_adapter)
        self.polynomial: PolynomialInstallation
        polynomial_adapters, self.polynomial = install_polynomial_capabilities(
            self.store,
            self.schemas,
            self.artifacts,
            self.checkers,
            authorize_checker=install_references,
        )
        for polynomial_adapter in polynomial_adapters:
            self.capabilities.register(polynomial_adapter)
        self.universal_algebra: UniversalAlgebraInstallation
        universal_algebra_adapters, self.universal_algebra = (
            install_universal_algebra_capabilities(
                self.store,
                self.schemas,
                self.artifacts,
                self.checkers,
                authorize_checker=install_references,
            )
        )
        for universal_algebra_adapter in universal_algebra_adapters:
            self.capabilities.register(universal_algebra_adapter)
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
            self.capabilities.register(LeanCheckAdapter(self.lean))
        for entrypoint in capability_adapter_entrypoints:
            self.capabilities.register(load_capability_adapter(entrypoint, self))

    def register_capability(self, adapter: CapabilityAdapter) -> None:
        """Install an operator-owned adapter without changing the kernel or MCP."""

        self.capabilities.register(adapter)
