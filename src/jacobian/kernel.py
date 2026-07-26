"""Application composition root for the v0.2 research kernel."""

from __future__ import annotations

import logging
from pathlib import Path

from jacobian.artifacts import ArtifactService
from jacobian.atomic_capabilities import install_atomic_capabilities
from jacobian.builtin_capabilities import (
    KnowledgeSearchAdapter,
    LeanCheckAdapter,
    LeanDeclarationInspectAdapter,
    LeanDeclarationSearchAdapter,
)
from jacobian.cadical import install_cadical_capabilities
from jacobian.capabilities import (
    CapabilityAdapter,
    CapabilityService,
    load_capability_adapter,
)
from jacobian.claims import ClaimValidationService
from jacobian.conjectures import ConjectureService
from jacobian.contracts.capabilities import (
    CapabilityProviderAvailability,
    CapabilityProviderRuntime,
)
from jacobian.contracts.lean import LeanEnvironment
from jacobian.cvc5 import install_cvc5_capability
from jacobian.evaluation import EvaluationService
from jacobian.experiment_router import ExperimentRouter
from jacobian.experiments import ExperimentService
from jacobian.finite_partition import (
    FinitePartitionInstallation,
    install_finite_partition,
)
from jacobian.graph_capabilities import GraphInstallation, install_graph_capabilities
from jacobian.lean import LeanService
from jacobian.lean_declarations import (
    LeanDeclarationService,
    installed_lean_declaration_service,
)
from jacobian.lean_exploration import (
    LeanExplorationInstallation,
    install_lean_exploration_capabilities,
)
from jacobian.matrix_capabilities import (
    MatrixInstallation,
    install_matrix_capabilities,
)
from jacobian.memory import ResearchMemory
from jacobian.plugin_execution import PluginExecutor
from jacobian.plugins.registry import PluginRegistry
from jacobian.polynomial_capabilities import (
    PolynomialInstallation,
    install_polynomial_capabilities,
)
from jacobian.polynomial_system_capabilities import (
    PolynomialSystemInstallation,
    install_polynomial_system_capabilities,
)
from jacobian.polytope import PolytopeService
from jacobian.provider_runtime import (
    cadical_provider_runtime,
    cvc5_provider_runtime,
    drat_trim_provider_runtime,
    lean_provider_runtime,
)
from jacobian.references import (
    LeanCheckerInstallation,
    PolytopeCheckerInstallation,
    ReferenceInstallation,
    ReferenceInstaller,
)
from jacobian.registry import CheckerRegistry
from jacobian.sat import SatArtifactService, install_sat_artifacts
from jacobian.sat_capabilities import (
    SatAssignmentCheckerInstallation,
    SatUnsatProofCheckerInstallation,
    install_sat_assignment_checker,
    install_sat_unsat_proof_checker,
)
from jacobian.schema_registry import SchemaRegistry
from jacobian.search import SearchService
from jacobian.shrinking import ShrinkService
from jacobian.smt import SmtArtifactService, install_smt_artifacts
from jacobian.store import ArtifactStore
from jacobian.structures import StructureService
from jacobian.transformations import TransformationService
from jacobian.universal_algebra_capabilities import (
    UniversalAlgebraInstallation,
    install_universal_algebra_capabilities,
)
from jacobian.verification import VerificationService
from jacobian.witnesses import WitnessSearchService
from jacobian.workspaces import WorkspaceService

_LOGGER = logging.getLogger(__name__)


class JacobianKernel:
    """Local v0.2 services over one content-addressed store."""

    def __init__(
        self,
        root: str | Path,
        *,
        install_references: bool = False,
        capability_adapter_entrypoints: tuple[str, ...] = (),
        capability_exclusions: frozenset[str] = frozenset(),
    ) -> None:
        # Construction-time exclusions support controlled portfolio ablations.
        # They are not a runtime authorization or access-control mechanism.
        self._capability_exclusions = capability_exclusions
        self.store = ArtifactStore(root)
        self.schemas = SchemaRegistry(self.store)
        self.artifacts = ArtifactService(self.store, self.schemas)
        self.sat: SatArtifactService = install_sat_artifacts(
            self.store,
            self.schemas,
            self.artifacts,
        )
        self.smt: SmtArtifactService = install_smt_artifacts(
            self.store,
            self.schemas,
            self.artifacts,
        )
        self.memory = ResearchMemory(self.store, self.schemas)
        self.workspaces = WorkspaceService(self.store, self.schemas)
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
        self.lean_declarations: LeanDeclarationService | None = None
        self.lean_exploration: LeanExplorationInstallation | None = None
        self.capabilities = CapabilityService(self.store, self.memory)
        self.sat_assignment_checker: SatAssignmentCheckerInstallation
        sat_assignment_adapter, self.sat_assignment_checker = (
            install_sat_assignment_checker(
                self.store,
                self.schemas,
                self.artifacts,
                self.sat,
                self.verification,
                self.checkers,
                authorize_checker=install_references,
            )
        )
        if sat_assignment_adapter is not None:
            self.register_capability(sat_assignment_adapter)
        self.drat_trim_runtime: CapabilityProviderRuntime = drat_trim_provider_runtime()
        self.sat_unsat_proof_checker: SatUnsatProofCheckerInstallation
        proof_adapter, self.sat_unsat_proof_checker = install_sat_unsat_proof_checker(
            self.store,
            self.schemas,
            self.artifacts,
            self.sat,
            self.verification,
            self.checkers,
            self.drat_trim_runtime,
            authorize_checker=install_references,
        )
        if proof_adapter is not None:
            self.register_capability(proof_adapter)
        self.cadical_runtime: CapabilityProviderRuntime = cadical_provider_runtime()
        if (
            self.cadical_runtime.availability
            is CapabilityProviderAvailability.AVAILABLE
        ):
            try:
                cadical_adapters = install_cadical_capabilities(
                    self.sat,
                    self.cadical_runtime,
                )
            except (OSError, ValueError) as exc:
                _LOGGER.warning(
                    "CaDiCaL SAT exploration is not installed: %s",
                    exc,
                )
            else:
                for cadical_adapter in cadical_adapters:
                    self.register_capability(cadical_adapter)
        self.cvc5_runtime: CapabilityProviderRuntime = cvc5_provider_runtime()
        if self.cvc5_runtime.availability is CapabilityProviderAvailability.AVAILABLE:
            try:
                cvc5_adapter = install_cvc5_capability(
                    self.smt,
                    self.cvc5_runtime,
                )
            except (OSError, ValueError) as exc:
                _LOGGER.warning(
                    "cvc5 SMT proof exploration is not installed: %s",
                    exc,
                )
            else:
                self.register_capability(cvc5_adapter)
        for atomic_adapter in install_atomic_capabilities(self):
            self.register_capability(atomic_adapter)
        self.register_capability(KnowledgeSearchAdapter(self.memory))
        self.finite_partition: FinitePartitionInstallation
        finite_partition, self.finite_partition = install_finite_partition(
            self.store,
            self.schemas,
            self.artifacts,
            self.verification,
            self.checkers,
            authorize_checker=install_references,
        )
        self.register_capability(finite_partition)
        self.graph: GraphInstallation
        graph_adapters, self.graph = install_graph_capabilities(
            self.store,
            self.schemas,
            self.artifacts,
            self.checkers,
            authorize_checker=install_references,
        )
        for graph_adapter in graph_adapters:
            self.register_capability(graph_adapter)
        self.polynomial: PolynomialInstallation
        polynomial_adapters, self.polynomial = install_polynomial_capabilities(
            self.store,
            self.schemas,
            self.artifacts,
            self.checkers,
            authorize_checker=install_references,
        )
        for polynomial_adapter in polynomial_adapters:
            self.register_capability(polynomial_adapter)
        self.matrix: MatrixInstallation
        matrix_adapters, self.matrix = install_matrix_capabilities(
            self.store,
            self.schemas,
            self.artifacts,
        )
        for matrix_adapter in matrix_adapters:
            self.register_capability(matrix_adapter)
        self.polynomial_system: PolynomialSystemInstallation
        polynomial_system_adapter, self.polynomial_system = (
            install_polynomial_system_capabilities(
                self.store,
                self.schemas,
                self.artifacts,
                self.verification,
                self.checkers,
                authorize_checker=install_references,
            )
        )
        if polynomial_system_adapter is not None:
            self.register_capability(polynomial_system_adapter)
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
            self.register_capability(universal_algebra_adapter)
        if install_references:
            self.references = self.reference_installer.install_all()
            self.polytope_checkers = self.reference_installer.install_polytope_checkers(
                claim_schema_uri=self.polytope.claim_schema_uri,
                semantics_uri=self.polytope.semantics_uri,
                point_schema_uri=self.polytope.point_schema_uri,
            )
            self.lean_checkers = self.reference_installer.install_lean_checkers()
            profiles = {
                environment.value: {
                    "semantics_uri": installation.semantics_uri,
                    "import_name": installation.import_name,
                    "mathlib_commit": installation.mathlib_commit,
                    "allowed_axioms": list(installation.allowed_axioms),
                    "checker_timeout_seconds": (installation.checker_timeout_seconds),
                }
                for environment, installation in sorted(
                    self.lean_checkers.items(),
                    key=lambda item: item[0].value,
                )
            }
            runtime = lean_provider_runtime(
                profiles=profiles,
                checker_ids=tuple(
                    installation.checker_id
                    for _, installation in sorted(
                        self.lean_checkers.items(),
                        key=lambda item: item[0].value,
                    )
                ),
            )
            if runtime.availability is CapabilityProviderAvailability.AVAILABLE:
                try:
                    self.lean_declarations = installed_lean_declaration_service(runtime)
                except (OSError, RuntimeError) as exc:
                    _LOGGER.warning(
                        "Lean declaration discovery is not installed: %s",
                        exc,
                    )
                if self.lean_declarations is not None:
                    self.register_capability(
                        LeanDeclarationSearchAdapter(
                            self.lean_declarations,
                            runtime,
                        )
                    )
                    self.register_capability(
                        LeanDeclarationInspectAdapter(
                            self.lean_declarations,
                            runtime,
                        )
                    )
                self.lean = LeanService(
                    self.store,
                    self.artifacts,
                    self.verification,
                    self.lean_checkers,
                )
                self.register_capability(LeanCheckAdapter(self.lean, runtime))
                lean_exploration_adapters, self.lean_exploration = (
                    install_lean_exploration_capabilities(
                        self.store,
                        self.schemas,
                        self.artifacts,
                        self.lean_checkers,
                        runtime,
                    )
                )
                for lean_exploration_adapter in lean_exploration_adapters:
                    self.register_capability(lean_exploration_adapter)
            else:
                _LOGGER.warning(
                    "lean.check is not installed: %s",
                    runtime.diagnostic,
                )
        for entrypoint in capability_adapter_entrypoints:
            self.register_capability(load_capability_adapter(entrypoint, self))

    def register_capability(self, adapter: CapabilityAdapter) -> None:
        """Install an operator-owned adapter without changing the kernel or MCP."""

        if adapter.descriptor.capability_id in self._capability_exclusions:
            return
        self.capabilities.register(adapter)
