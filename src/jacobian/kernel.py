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
from jacobian.domain_atomic_extras import install_domain_atomic_extras
from jacobian.evaluation import EvaluationService
from jacobian.experiment_router import ExperimentRouter
from jacobian.experiments import ExperimentService
from jacobian.finite_partition import (
    FinitePartitionInstallation,
    install_finite_partition,
)
from jacobian.flint_hnf import install_python_flint_hnf_capability
from jacobian.flint_linear import (
    install_python_flint_inconsistency_capability,
    install_python_flint_linear_capability,
)
from jacobian.geometry_capabilities import install_geometry_capabilities
from jacobian.graph_capabilities import GraphInstallation, install_graph_capabilities
from jacobian.graph_coloring_capabilities import (
    GraphColoringInstallation,
    install_graph_coloring_capabilities,
)
from jacobian.graph_composition_capabilities import (
    GraphCompositionInstallation,
    install_graph_composition_capabilities,
)
from jacobian.graph_isomorphism import (
    GraphIsomorphismInstallation,
    install_graph_isomorphism,
)
from jacobian.lean import LeanService
from jacobian.lean_declarations import (
    LeanDeclarationService,
    installed_lean_declaration_service,
)
from jacobian.lean_exploration import (
    LeanExplorationInstallation,
    install_lean_exploration_capabilities,
)
from jacobian.lean_statement_capabilities import (
    LeanStatementInstallation,
    install_lean_statement_capabilities,
)
from jacobian.linear import LinearArtifactService, install_linear_artifacts
from jacobian.linear_capabilities import (
    LinearRationalInconsistencyCheckerInstallation,
    LinearRationalSolutionCheckerInstallation,
    install_linear_rational_inconsistency_checker,
    install_linear_rational_solution_checker,
)
from jacobian.matrix_capabilities import (
    MatrixInstallation,
    install_matrix_capabilities,
)
from jacobian.matrix_determinant_capabilities import (
    MatrixDeterminantCheckerInstallation,
    install_matrix_determinant_checker,
)
from jacobian.matrix_normal_form_capabilities import (
    MatrixNormalFormCheckerInstallation,
    install_matrix_normal_form_checker,
)
from jacobian.matrix_normal_forms import (
    MatrixNormalFormArtifactService,
    install_matrix_normal_form_artifacts,
)
from jacobian.memory import ResearchMemory
from jacobian.plugin_execution import PluginExecutor
from jacobian.plugins.registry import PluginRegistry
from jacobian.polynomial_capabilities import (
    PolynomialInstallation,
    install_polynomial_capabilities,
)
from jacobian.polynomial_expression_capabilities import (
    PolynomialExpressionCheckerInstallation,
    install_polynomial_expression_checker,
)
from jacobian.polynomial_expressions import (
    PolynomialExpressionArtifactService,
    install_polynomial_expression_artifacts,
)
from jacobian.polynomial_interval_capabilities import (
    PolynomialIntervalInstallation,
    install_polynomial_interval_capabilities,
)
from jacobian.polynomial_positivity_capabilities import (
    PolynomialPositivityInstallation,
    install_polynomial_positivity_capabilities,
)
from jacobian.polynomial_system_capabilities import (
    PolynomialSystemInstallation,
    install_polynomial_system_capabilities,
)
from jacobian.polytope import PolytopeService
from jacobian.primitive_adapters import factory as install_primitive_adapters
from jacobian.primitive_math_capabilities import install_primitive_math_capabilities
from jacobian.provider_runtime import (
    cadical_provider_runtime,
    carcara_provider_runtime,
    cvc5_provider_runtime,
    drat_trim_provider_runtime,
    lean_provider_runtime,
    python_flint_hnf_provider_runtime,
    python_flint_provider_runtime,
    sympy_polynomial_normalization_provider_runtime,
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
from jacobian.smt_capabilities import (
    SmtUnsatProofCheckerInstallation,
    install_smt_unsat_proof_checker,
)
from jacobian.store import ArtifactStore
from jacobian.structures import StructureService
from jacobian.sympy_polynomial_normalization import (
    install_sympy_polynomial_normalization_capability,
)
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
        self.linear: LinearArtifactService = install_linear_artifacts(
            self.store,
            self.schemas,
            self.artifacts,
        )
        self.matrix_normal_forms: MatrixNormalFormArtifactService = (
            install_matrix_normal_form_artifacts(
                self.store,
                self.schemas,
                self.artifacts,
            )
        )
        self.polynomial_expressions: PolynomialExpressionArtifactService = (
            install_polynomial_expression_artifacts(
                self.store,
                self.schemas,
                self.artifacts,
            )
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
        self.carcara_runtime: CapabilityProviderRuntime = carcara_provider_runtime()
        self.smt_unsat_proof_checker: SmtUnsatProofCheckerInstallation
        smt_proof_adapter, self.smt_unsat_proof_checker = (
            install_smt_unsat_proof_checker(
                self.store,
                self.schemas,
                self.artifacts,
                self.smt,
                self.verification,
                self.checkers,
                self.carcara_runtime,
                authorize_checker=install_references,
            )
        )
        if smt_proof_adapter is not None:
            self.register_capability(smt_proof_adapter)
        self.linear_solution_checker: LinearRationalSolutionCheckerInstallation
        linear_verification_adapter, self.linear_solution_checker = (
            install_linear_rational_solution_checker(
                self.store,
                self.schemas,
                self.artifacts,
                self.linear,
                self.verification,
                self.checkers,
                authorize_checker=install_references,
            )
        )
        if linear_verification_adapter is not None:
            self.register_capability(linear_verification_adapter)
        self.linear_inconsistency_checker: (
            LinearRationalInconsistencyCheckerInstallation
        )
        (
            linear_inconsistency_verification_adapter,
            self.linear_inconsistency_checker,
        ) = install_linear_rational_inconsistency_checker(
            self.store,
            self.schemas,
            self.artifacts,
            self.linear,
            self.verification,
            self.checkers,
            authorize_checker=install_references,
        )
        if linear_inconsistency_verification_adapter is not None:
            self.register_capability(linear_inconsistency_verification_adapter)
        self._install_python_flint_capabilities()
        self._install_matrix_normal_form_capabilities(
            authorize_checker=install_references
        )
        self._install_polynomial_expression_capabilities(
            authorize_checker=install_references
        )
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
        self._install_graph_coloring_capabilities(install_references)
        self._install_geometry_capabilities()
        self.graph_isomorphism: GraphIsomorphismInstallation
        graph_isomorphism, self.graph_isomorphism = install_graph_isomorphism(
            self.store,
            self.schemas,
            self.artifacts,
            self.verification,
            self.checkers,
            self.graph,
            authorize_checker=install_references,
        )
        if graph_isomorphism is not None:
            self.register_capability(graph_isomorphism)
        self.polynomial: PolynomialInstallation
        polynomial_adapters, self.polynomial = install_polynomial_capabilities(
            self.store,
            self.schemas,
            self.artifacts,
            self.verification,
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
        self.matrix_determinant_checker: MatrixDeterminantCheckerInstallation
        determinant_verification, self.matrix_determinant_checker = (
            install_matrix_determinant_checker(
                self.store,
                self.schemas,
                self.artifacts,
                self.matrix,
                self.verification,
                self.checkers,
                authorize_checker=install_references,
            )
        )
        if determinant_verification is not None:
            self.register_capability(determinant_verification)
        self._install_primitive_math_capabilities()
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
        self._install_resource_capabilities(install_references)
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

    def _install_resource_capabilities(self, install_references: bool) -> None:
        """Install resource-mined domain atomics after core services exist."""
        self.graph_composition: GraphCompositionInstallation
        graph_adapters, self.graph_composition = install_graph_composition_capabilities(
            self.store,
            self.schemas,
            self.artifacts,
            semantics_uri=self.graph.semantics_uri,
            graph_schema_uri=self.graph.graph_schema_uri,
        )
        for adapter in graph_adapters:
            self.register_capability(adapter)

        self.polynomial_interval: PolynomialIntervalInstallation
        interval_adapters, self.polynomial_interval = (
            install_polynomial_interval_capabilities(
                self.store,
                self.schemas,
                self.artifacts,
                self.verification,
                self.checkers,
                authorize_checker=install_references,
            )
        )
        for interval_adapter in interval_adapters:
            if interval_adapter is not None:
                self.register_capability(interval_adapter)

        self.polynomial_positivity: PolynomialPositivityInstallation
        positivity_adapters, self.polynomial_positivity = (
            install_polynomial_positivity_capabilities(
                self.store,
                self.schemas,
                self.artifacts,
                self.verification,
                self.checkers,
                authorize_checker=install_references,
            )
        )
        for positivity_adapter in positivity_adapters:
            if positivity_adapter is not None:
                self.register_capability(positivity_adapter)

        self.lean_statement: LeanStatementInstallation
        lean_adapters, self.lean_statement = install_lean_statement_capabilities(
            self.store,
            self.schemas,
            self.artifacts,
        )
        for lean_statement_adapter in lean_adapters:
            self.register_capability(lean_statement_adapter)
        for primitive_adapter in install_primitive_adapters(self):
            self.register_capability(primitive_adapter)
        for domain_atomic_adapter in install_domain_atomic_extras(self):
            self.register_capability(domain_atomic_adapter)

    def _install_graph_coloring_capabilities(self, authorize_checker: bool) -> None:
        self.graph_coloring: GraphColoringInstallation
        graph_coloring_adapters, self.graph_coloring = (
            install_graph_coloring_capabilities(
                self.store,
                self.schemas,
                self.artifacts,
                self.sat,
                self.checkers,
                authorize_checker=authorize_checker,
            )
        )
        for graph_coloring_adapter in graph_coloring_adapters:
            self.register_capability(graph_coloring_adapter)

    def _install_matrix_normal_form_capabilities(
        self,
        *,
        authorize_checker: bool,
    ) -> None:
        self.matrix_normal_form_checker: MatrixNormalFormCheckerInstallation
        verification_adapter, self.matrix_normal_form_checker = (
            install_matrix_normal_form_checker(
                self.store,
                self.schemas,
                self.artifacts,
                self.matrix_normal_forms,
                self.verification,
                self.checkers,
                authorize_checker=authorize_checker,
            )
        )
        if verification_adapter is not None:
            self.register_capability(verification_adapter)

        self.python_flint_hnf_runtime: CapabilityProviderRuntime = (
            python_flint_hnf_provider_runtime()
        )
        if (
            self.python_flint_hnf_runtime.availability
            is not CapabilityProviderAvailability.AVAILABLE
        ):
            return
        try:
            adapter = install_python_flint_hnf_capability(
                self.matrix_normal_forms,
                self.python_flint_hnf_runtime,
            )
        except (OSError, ValueError) as exc:
            _LOGGER.warning(
                "Python-FLINT Hermite normal form is not installed: %s",
                exc,
            )
        else:
            self.register_capability(adapter)

    def _install_primitive_math_capabilities(self) -> None:
        for adapter in install_primitive_math_capabilities(
            self.store,
            self.schemas,
            self.artifacts,
        ):
            self.register_capability(adapter)

    def _install_geometry_capabilities(self) -> None:
        for adapter in install_geometry_capabilities(
            self.store,
            self.schemas,
            self.artifacts,
        ):
            self.register_capability(adapter)

    def _install_python_flint_capabilities(self) -> None:
        """Install exact rational linear producers when the pin is available."""

        self.python_flint_runtime = python_flint_provider_runtime()
        if (
            self.python_flint_runtime.availability
            is not CapabilityProviderAvailability.AVAILABLE
        ):
            return
        try:
            solution_adapter = install_python_flint_linear_capability(
                self.linear,
                self.python_flint_runtime,
            )
        except (OSError, ValueError) as exc:
            _LOGGER.warning(
                "Python-FLINT rational solution exploration is not installed: %s",
                exc,
            )
        else:
            self.register_capability(solution_adapter)
        try:
            inconsistency_adapter = install_python_flint_inconsistency_capability(
                self.linear,
                self.python_flint_runtime,
            )
        except (OSError, ValueError) as exc:
            _LOGGER.warning(
                "Python-FLINT rational inconsistency exploration is not installed: %s",
                exc,
            )
        else:
            self.register_capability(inconsistency_adapter)

    def _install_polynomial_expression_capabilities(
        self,
        *,
        authorize_checker: bool,
    ) -> None:
        self.polynomial_expression_checker: PolynomialExpressionCheckerInstallation
        verification_adapter, self.polynomial_expression_checker = (
            install_polynomial_expression_checker(
                self.store,
                self.schemas,
                self.artifacts,
                self.polynomial_expressions,
                self.verification,
                self.checkers,
                authorize_checker=authorize_checker,
            )
        )
        if verification_adapter is not None:
            self.register_capability(verification_adapter)

        self.sympy_polynomial_normalization_runtime: CapabilityProviderRuntime = (
            sympy_polynomial_normalization_provider_runtime()
        )
        if (
            self.sympy_polynomial_normalization_runtime.availability
            is not CapabilityProviderAvailability.AVAILABLE
        ):
            return
        try:
            adapter = install_sympy_polynomial_normalization_capability(
                self.polynomial_expressions,
                self.sympy_polynomial_normalization_runtime,
            )
        except (OSError, ValueError) as exc:
            _LOGGER.warning(
                "SymPy typed polynomial normalization is not installed: %s",
                exc,
            )
        else:
            self.register_capability(adapter)

    def register_capability(self, adapter: CapabilityAdapter) -> None:
        """Install an operator-owned adapter without changing the kernel or MCP."""

        if adapter.descriptor.capability_id in self._capability_exclusions:
            return
        self.capabilities.register(adapter)
