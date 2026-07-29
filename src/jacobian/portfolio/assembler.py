"""Installation of the complete built-in mathematical portfolio.

The assembler installs the full built-in capability/checker/provider portfolio
through one narrow infrastructure context plus the application service graph.
It performs no discovery, registration, ranking, or verification authorization
beyond what the individual installers do.

Per the fail-closed ownership model, the only legitimate per-bundle omission is
a declared unavailable provider: an unavailable optional provider removes only
its own bundle, leaving the rest of the portfolio installed. Every other
installation failure (programming, schema, store, or configuration defects)
propagates so the caller's enclosing transaction rolls back atomically rather
than leaving a partially-constructed, silently-degraded portfolio.

The assembler never imports or accepts ``JacobianRuntime`` and never creates a
facade. It depends only on ``InstallationContext``, ``ApplicationServices``,
and explicit capability entrypoints/exclusions.
"""

from __future__ import annotations

import importlib
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from jacobian.atomic_capabilities import install_atomic_capabilities
from jacobian.builtin_capabilities import (
    KnowledgeSearchAdapter,
    LeanCheckAdapter,
    LeanDeclarationInspectAdapter,
    LeanDeclarationSearchAdapter,
    LeanDependencyGraphAdapter,
)
from jacobian.cadical import install_cadical_capabilities
from jacobian.capabilities import CapabilityAdapter, CapabilityError
from jacobian.contracts.capabilities import (
    CapabilityDescriptor,
    CapabilityProviderAvailability,
    CapabilityProviderRuntime,
)
from jacobian.contracts.lean import LeanDependencyGraphArtifact
from jacobian.cvc5 import install_cvc5_capability
from jacobian.exact_domain_checkers import install_exact_domain_verification
from jacobian.finite_coverage import install_finite_coverage
from jacobian.finite_partition import install_finite_partition
from jacobian.flint_hnf import install_python_flint_hnf_capability
from jacobian.flint_linear import (
    install_python_flint_inconsistency_capability,
    install_python_flint_linear_capability,
)
from jacobian.geometry_verification import install_geometry_checker
from jacobian.graph_capabilities import install_graph_capabilities
from jacobian.graph_coloring_capabilities import (
    install_graph_coloring_capabilities,
)
from jacobian.graph_composition_capabilities import (
    install_graph_composition_capabilities,
)
from jacobian.graph_isomorphism import install_graph_isomorphism
from jacobian.graph_shrinking import install_graph_shrinking
from jacobian.installation.context import InstallationContext
from jacobian.lean import LeanService
from jacobian.lean_declarations import (
    installed_lean_declaration_service,
)
from jacobian.lean_exploration import install_lean_exploration_capabilities
from jacobian.lean_proof_edit import install_lean_proof_edit_capability
from jacobian.lean_statement_capabilities import (
    install_lean_statement_capabilities,
)
from jacobian.linear_capabilities import (
    install_linear_rational_inconsistency_checker,
    install_linear_rational_solution_checker,
)
from jacobian.matrix_capabilities import install_matrix_capabilities
from jacobian.matrix_determinant_capabilities import (
    install_matrix_determinant_checker,
)
from jacobian.matrix_normal_form_capabilities import (
    install_matrix_normal_form_checker,
)
from jacobian.matrix_rank_capabilities import install_matrix_rank_checker
from jacobian.operation_installation import InstalledDomainBundle
from jacobian.polynomial_capabilities import install_polynomial_capabilities
from jacobian.polynomial_expression_capabilities import (
    install_polynomial_expression_checker,
)
from jacobian.polynomial_interval_capabilities import (
    install_polynomial_interval_capabilities,
)
from jacobian.polynomial_positivity_capabilities import (
    install_polynomial_positivity_capabilities,
)
from jacobian.polynomial_system_capabilities import (
    install_polynomial_system_capabilities,
)
from jacobian.polynomial_system_search import PolynomialSystemRationalSearchAdapter
from jacobian.portfolio.builtin import BUILTIN_PORTFOLIO
from jacobian.portfolio.model import PortfolioPlan
from jacobian.portfolio.result import (
    PROVIDER_UNAVAILABLE,
    BundleInstallation,
    BundleInstallationStatus,
    PortfolioDiagnostic,
    PortfolioInstallation,
    PortfolioInstallationResult,
)
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
from jacobian.references import REFERENCE_INSTALLATION_DOMAINS
from jacobian.runtime.config import CheckerAuthorityMode
from jacobian.runtime.services import ApplicationServices, CoreServices
from jacobian.sat_capabilities import (
    SatCnfMaterializationAdapter,
    install_sat_assignment_checker,
    install_sat_unsat_proof_checker,
)
from jacobian.sat_lrat_capabilities import install_sat_lrat_verifier
from jacobian.smt_capabilities import install_smt_unsat_proof_checker
from jacobian.sympy_polynomial_normalization import (
    install_sympy_polynomial_normalization_capability,
)
from jacobian.universal_algebra_capabilities import (
    install_universal_algebra_capabilities,
)

_LOGGER = logging.getLogger(__name__)

_ENTRYPOINT_SEPARATOR = ":"
_ENTRYPOINT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$")

# Expected import-time failures for capability adapter entrypoint loading.
_ENTRYPOINT_ERRORS: tuple[type[BaseException], ...] = (
    AttributeError,
    ImportError,
    TypeError,
)

type CapabilityRegistrar = Callable[[CapabilityAdapter], None]


@dataclass(slots=True)
class PortfolioAssembler:
    """Install the complete built-in portfolio through one narrow context.

    The assembler owns no state beyond the ``InstallationContext``. The full
    ``install`` method is the primary entry point; ``install_domains`` remains
    for standalone domain-bundle installation and is called internally by
    ``install``.
    """

    context: InstallationContext

    # ------------------------------------------------------------------
    # Full portfolio installation
    # ------------------------------------------------------------------

    def install(
        self,
        application: ApplicationServices,
        *,
        capability_adapter_entrypoints: tuple[str, ...] = (),
    ) -> PortfolioInstallation:
        """Install the complete built-in portfolio and return typed results.

        This method absorbs every step previously embedded in
        ``JacobianRuntime._install_capability_portfolio`` and its helper
        methods. The caller must wrap the call in its own checker-policy,
        store, and package-digest transaction; this method performs no
        transaction management.

        Only declared optional provider unavailability may omit affected
        capabilities. Every other failure propagates so the caller's
        transaction rolls back atomically.
        """

        ctx = self.context
        core = application.core
        result = PortfolioInstallation()
        authorize = ctx.authorizes_bundled_checkers

        def register(adapter: CapabilityAdapter) -> None:
            ctx.register_capability(adapter)

        # --- SAT ---
        register(SatCnfMaterializationAdapter(core.sat))
        sat_assignment_adapter, result.sat_assignment_checker = (
            install_sat_assignment_checker(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                core.sat,
                ctx.verification,
                ctx.checkers,
                authorize_checker=authorize,
            )
        )
        if sat_assignment_adapter is not None:
            register(sat_assignment_adapter)

        result.drat_trim_runtime = drat_trim_provider_runtime()
        proof_adapter, result.sat_unsat_proof_checker = install_sat_unsat_proof_checker(
            ctx.store,
            ctx.schemas,
            ctx.artifacts,
            core.sat,
            ctx.verification,
            ctx.checkers,
            result.drat_trim_runtime,
            authorize_checker=authorize,
        )
        if proof_adapter is not None:
            register(proof_adapter)

        lrat_adapter, result.sat_lrat = install_sat_lrat_verifier(
            ctx.store,
            ctx.schemas,
            ctx.artifacts,
            core.sat,
            ctx.verification,
            ctx.checkers,
            authorize_checker=authorize,
        )
        if lrat_adapter is not None:
            register(lrat_adapter)

        # --- SMT ---
        result.carcara_runtime = carcara_provider_runtime()
        smt_proof_adapter, result.smt_unsat_proof_checker = (
            install_smt_unsat_proof_checker(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                core.smt,
                ctx.verification,
                ctx.checkers,
                result.carcara_runtime,
                authorize_checker=authorize,
            )
        )
        if smt_proof_adapter is not None:
            register(smt_proof_adapter)

        # --- Linear ---
        linear_verification_adapter, result.linear_solution_checker = (
            install_linear_rational_solution_checker(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                core.linear,
                ctx.verification,
                ctx.checkers,
                authorize_checker=authorize,
            )
        )
        if linear_verification_adapter is not None:
            register(linear_verification_adapter)

        (
            linear_inconsistency_verification_adapter,
            result.linear_inconsistency_checker,
        ) = install_linear_rational_inconsistency_checker(
            ctx.store,
            ctx.schemas,
            ctx.artifacts,
            core.linear,
            ctx.verification,
            ctx.checkers,
            authorize_checker=authorize,
        )
        if linear_inconsistency_verification_adapter is not None:
            register(linear_inconsistency_verification_adapter)

        self._install_python_flint_capabilities(core, result, register)
        self._install_matrix_normal_form_capabilities(
            core, result, register, authorize_checker=authorize
        )
        self._install_polynomial_expression_capabilities(
            core, result, register, authorize_checker=authorize
        )

        self._install_external_solver_capabilities(core, result, register)

        # --- Atomic / claim decomposition / knowledge search ---
        for atomic_adapter in install_atomic_capabilities(ctx, application):
            register(atomic_adapter)
        for claim_decomposition_adapter in application.claim_decomposition_adapters:
            register(claim_decomposition_adapter)
        register(KnowledgeSearchAdapter(core.memory))

        # --- Finite partition / coverage ---
        finite_partition_adapter, result.finite_partition = install_finite_partition(
            ctx.store,
            ctx.schemas,
            ctx.artifacts,
            ctx.verification,
            ctx.checkers,
            authorize_checker=authorize,
        )
        register(finite_partition_adapter)

        finite_coverage_adapter, result.finite_coverage = install_finite_coverage(
            ctx.store,
            ctx.schemas,
            ctx.artifacts,
            ctx.verification,
            ctx.checkers,
            authorize_checker=authorize,
        )
        if finite_coverage_adapter is not None:
            register(finite_coverage_adapter)

        # --- Graph ---
        graph_adapters, result.graph = install_graph_capabilities(
            ctx.store,
            ctx.schemas,
            ctx.artifacts,
            ctx.checkers,
            authorize_checker=authorize,
        )
        for graph_adapter in graph_adapters:
            register(graph_adapter)

        graph_shrinking_adapter, result.graph_shrinking = install_graph_shrinking(
            ctx.store,
            ctx.schemas,
            ctx.artifacts,
            core.plugins,
            ctx.checkers,
            application.shrinking,
            result.graph,
            application.reference_installer,
            authorize_checker=authorize,
        )
        register(graph_shrinking_adapter)

        self._install_graph_coloring_capabilities(
            core, result, register, authorize_checker=authorize
        )

        # --- Domain bundles ---
        self._install_builtin_domain_bundles(result)

        # --- Domain verification ---
        self._install_builtin_domain_verification(
            ctx, result, register, authorize=authorize
        )

        # --- Graph isomorphism ---
        graph_isomorphism_adapter, result.graph_isomorphism = install_graph_isomorphism(
            ctx.store,
            ctx.schemas,
            ctx.artifacts,
            ctx.verification,
            ctx.checkers,
            result.graph,
            authorize_checker=authorize,
        )
        if graph_isomorphism_adapter is not None:
            register(graph_isomorphism_adapter)

        # --- Polynomial ---
        polynomial_adapters, result.polynomial = install_polynomial_capabilities(
            ctx.store,
            ctx.schemas,
            ctx.artifacts,
            ctx.verification,
            ctx.checkers,
            authorize_checker=authorize,
        )
        for polynomial_adapter in polynomial_adapters:
            register(polynomial_adapter)

        # --- Matrix ---
        matrix_adapters, result.matrix = install_matrix_capabilities(
            ctx.store,
            ctx.schemas,
            ctx.artifacts,
        )
        for matrix_adapter in matrix_adapters:
            register(matrix_adapter)

        determinant_verification, result.matrix_determinant_checker = (
            install_matrix_determinant_checker(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                result.matrix,
                ctx.verification,
                ctx.checkers,
                authorize_checker=authorize,
            )
        )
        if determinant_verification is not None:
            register(determinant_verification)

        rank_verification, result.matrix_rank_checker = install_matrix_rank_checker(
            ctx.store,
            ctx.schemas,
            ctx.artifacts,
            result.matrix,
            ctx.verification,
            ctx.checkers,
            authorize_checker=authorize,
        )
        if rank_verification is not None:
            register(rank_verification)

        # --- Polynomial system ---
        polynomial_system_adapter, result.polynomial_system = (
            install_polynomial_system_capabilities(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                ctx.verification,
                ctx.checkers,
                authorize_checker=authorize,
            )
        )
        if polynomial_system_adapter is not None:
            register(polynomial_system_adapter)
        register(
            PolynomialSystemRationalSearchAdapter(
                ctx.artifacts, result.polynomial_system
            )
        )

        # --- Universal algebra ---
        universal_algebra_adapters, result.universal_algebra = (
            install_universal_algebra_capabilities(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                ctx.checkers,
                authorize_checker=authorize,
            )
        )
        for universal_algebra_adapter in universal_algebra_adapters:
            register(universal_algebra_adapter)

        # --- Resource capabilities ---
        self._install_resource_capabilities(
            ctx, core, result, register, authorize=authorize
        )

        # --- Authorized references ---
        if authorize or (
            ctx.checker_authority is CheckerAuthorityMode.HYDRATE_EXISTING
            and core.plugins.has_any_domain(REFERENCE_INSTALLATION_DOMAINS)
        ):
            self._install_authorized_references(ctx, application, result, register)

        # --- Capability adapter entrypoints ---
        for entrypoint in capability_adapter_entrypoints:
            register(self._load_entrypoint_adapter(entrypoint, application))

        return result

    def _install_external_solver_capabilities(
        self,
        core: CoreServices,
        result: PortfolioInstallation,
        register: CapabilityRegistrar,
    ) -> None:
        """Install capabilities backed by declared optional solver providers."""

        result.cadical_runtime = cadical_provider_runtime()
        if (
            result.cadical_runtime.availability
            is CapabilityProviderAvailability.AVAILABLE
        ):
            try:
                cadical_adapters = install_cadical_capabilities(
                    core.sat,
                    result.cadical_runtime,
                )
            except OSError as exc:
                _LOGGER.warning("CaDiCaL SAT exploration is not installed: %s", exc)
            else:
                for adapter in cadical_adapters:
                    register(adapter)

        result.cvc5_runtime = cvc5_provider_runtime()
        if result.cvc5_runtime.availability is CapabilityProviderAvailability.AVAILABLE:
            try:
                adapter = install_cvc5_capability(core.smt, result.cvc5_runtime)
            except OSError as exc:
                _LOGGER.warning("cvc5 SMT proof exploration is not installed: %s", exc)
            else:
                register(adapter)

    # ------------------------------------------------------------------
    # Domain-bundle-only installation (used internally and standalone)
    # ------------------------------------------------------------------

    def install_domains(self, plan: PortfolioPlan) -> PortfolioInstallationResult:
        """Install every bundle in ``plan`` and return typed per-bundle outcomes.

        The plan is validated first; structural defects fail fast. Each bundle
        is then installed in declaration order:

        * a bundle whose provider runtime is declared unavailable records a
          ``PROVIDER_UNAVAILABLE`` diagnostic and is omitted from ``installed``,
          removing only that bundle's capabilities while the rest of the
          portfolio stays installed;
        * any other installation failure propagates so the caller's enclosing
          transaction rolls back the partial portfolio atomically.

        Diagnostics are non-conclusive: a skipped bundle is absent from
        ``installed`` and never promoted to installed.
        """

        plan.validate()
        installed: dict[str, InstalledDomainBundle] = {}
        diagnostics: list[PortfolioDiagnostic] = []
        outcomes: list[BundleInstallation] = []
        for bundle in plan.domain_bundles:
            capability_ids = tuple(
                operation.capability_id for operation in bundle.capabilities
            )
            runtime = bundle.provider_runtime
            if runtime.availability is not CapabilityProviderAvailability.AVAILABLE:
                diagnostic = PortfolioDiagnostic(
                    code=PROVIDER_UNAVAILABLE,
                    component_id=bundle.domain_id,
                    stage="provider_availability",
                    message=runtime.diagnostic or f"{runtime.provider} is unavailable",
                )
                diagnostics.append(diagnostic)
                outcomes.append(
                    BundleInstallation(
                        domain_id=bundle.domain_id,
                        status=BundleInstallationStatus.SKIPPED_PROVIDER_UNAVAILABLE,
                        capability_ids=capability_ids,
                        installed=None,
                        diagnostic=diagnostic,
                    )
                )
                continue
            installation = self.context.operations.install(bundle)
            installed[bundle.domain_id] = installation
            for adapter in installation.adapters:
                self.context.register_capability(adapter)
            outcomes.append(
                BundleInstallation(
                    domain_id=bundle.domain_id,
                    status=BundleInstallationStatus.INSTALLED,
                    capability_ids=capability_ids,
                    installed=installation,
                    diagnostic=None,
                )
            )
        return PortfolioInstallationResult(
            installed=installed,
            diagnostics=tuple(diagnostics),
            outcomes=tuple(outcomes),
        )

    # ------------------------------------------------------------------
    # Private installation helpers
    # ------------------------------------------------------------------

    def _install_python_flint_capabilities(
        self,
        core: CoreServices,
        result: PortfolioInstallation,
        register: CapabilityRegistrar,
    ) -> None:
        """Install exact rational linear producers when the pin is available."""

        result.python_flint_runtime = python_flint_provider_runtime()
        if (
            result.python_flint_runtime.availability
            is not CapabilityProviderAvailability.AVAILABLE
        ):
            return
        try:
            solution_adapter = install_python_flint_linear_capability(
                core.linear,
                result.python_flint_runtime,
            )
        except (OSError, ValueError) as exc:
            _LOGGER.warning(
                "Python-FLINT rational solution exploration is not installed: %s",
                exc,
            )
        else:
            register(solution_adapter)
        try:
            inconsistency_adapter = install_python_flint_inconsistency_capability(
                core.linear,
                result.python_flint_runtime,
            )
        except (OSError, ValueError) as exc:
            _LOGGER.warning(
                "Python-FLINT rational inconsistency exploration is not installed: %s",
                exc,
            )
        else:
            register(inconsistency_adapter)

    def _install_matrix_normal_form_capabilities(
        self,
        core: CoreServices,
        result: PortfolioInstallation,
        register: CapabilityRegistrar,
        *,
        authorize_checker: bool,
    ) -> None:
        ctx = self.context
        verification_adapter, result.matrix_normal_form_checker = (
            install_matrix_normal_form_checker(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                core.matrix_normal_forms,
                ctx.verification,
                ctx.checkers,
                authorize_checker=authorize_checker,
            )
        )
        if verification_adapter is not None:
            register(verification_adapter)

        result.python_flint_hnf_runtime = python_flint_hnf_provider_runtime()
        if (
            result.python_flint_hnf_runtime.availability
            is not CapabilityProviderAvailability.AVAILABLE
        ):
            return
        try:
            adapter = install_python_flint_hnf_capability(
                core.matrix_normal_forms,
                result.python_flint_hnf_runtime,
            )
        except (OSError, ValueError) as exc:
            _LOGGER.warning(
                "Python-FLINT Hermite normal form is not installed: %s",
                exc,
            )
        else:
            register(adapter)

    def _install_polynomial_expression_capabilities(
        self,
        core: CoreServices,
        result: PortfolioInstallation,
        register: CapabilityRegistrar,
        *,
        authorize_checker: bool,
    ) -> None:
        ctx = self.context
        verification_adapter, result.polynomial_expression_checker = (
            install_polynomial_expression_checker(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                core.polynomial_expressions,
                ctx.verification,
                ctx.checkers,
                authorize_checker=authorize_checker,
            )
        )
        if verification_adapter is not None:
            register(verification_adapter)

        result.sympy_polynomial_normalization_runtime = (
            sympy_polynomial_normalization_provider_runtime()
        )
        if (
            result.sympy_polynomial_normalization_runtime.availability
            is not CapabilityProviderAvailability.AVAILABLE
        ):
            return
        try:
            adapter = install_sympy_polynomial_normalization_capability(
                core.polynomial_expressions,
                result.sympy_polynomial_normalization_runtime,
            )
        except (OSError, ValueError) as exc:
            _LOGGER.warning(
                "SymPy typed polynomial normalization is not installed: %s",
                exc,
            )
        else:
            register(adapter)

    def _install_graph_coloring_capabilities(
        self,
        core: CoreServices,
        result: PortfolioInstallation,
        register: CapabilityRegistrar,
        *,
        authorize_checker: bool,
    ) -> None:
        ctx = self.context
        graph_coloring_adapters, result.graph_coloring = (
            install_graph_coloring_capabilities(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                core.sat,
                ctx.checkers,
                authorize_checker=authorize_checker,
            )
        )
        for graph_coloring_adapter in graph_coloring_adapters:
            register(graph_coloring_adapter)

    def _install_builtin_domain_bundles(
        self,
        result: PortfolioInstallation,
    ) -> None:
        bundle_result = self.install_domains(BUILTIN_PORTFOLIO)
        result.domain_bundles = dict(bundle_result.installed)
        result.portfolio_diagnostics = bundle_result.diagnostics
        result.portfolio_outcomes = bundle_result.outcomes

    def _install_builtin_domain_verification(
        self,
        ctx: InstallationContext,
        result: PortfolioInstallation,
        register: CapabilityRegistrar,
        *,
        authorize: bool,
    ) -> None:
        geometry = result.domain_bundles.get("geometry")
        if geometry is not None:
            geometry_adapter, result.geometry_checker = install_geometry_checker(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                geometry,
                ctx.verification,
                ctx.checkers,
                authorize_checker=authorize,
            )
            if geometry_adapter is not None:
                register(geometry_adapter)

        polynomial = result.domain_bundles.get("polynomial")
        matrix = result.domain_bundles.get("matrix")
        graph = result.domain_bundles.get("graph_optimization")
        graph_invariants = result.domain_bundles.get("graph_invariants")
        number_theory = result.domain_bundles.get("number_theory")
        projective_geometry = result.domain_bundles.get("projective_geometry")
        if polynomial is None or matrix is None:
            return
        adapters, result.exact_domain_checkers = install_exact_domain_verification(
            ctx.store,
            ctx.schemas,
            ctx.artifacts,
            ctx.verification,
            ctx.checkers,
            polynomial=polynomial,
            matrix=matrix,
            graph=graph,
            graph_invariants=graph_invariants,
            number_theory=number_theory,
            projective_geometry=projective_geometry,
            authorize=authorize,
        )
        for adapter in adapters:
            register(adapter)

    def _install_resource_capabilities(
        self,
        ctx: InstallationContext,
        core: CoreServices,
        result: PortfolioInstallation,
        register: CapabilityRegistrar,
        *,
        authorize: bool,
    ) -> None:
        """Install resource-mined domain atomics after core services exist."""

        if result.graph is None:
            raise RuntimeError("graph capabilities must precede resource installation")
        graph_adapters, result.graph_composition = (
            install_graph_composition_capabilities(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                semantics_uri=result.graph.semantics_uri,
                graph_schema_uri=result.graph.graph_schema_uri,
            )
        )
        for adapter in graph_adapters:
            register(adapter)

        interval_adapters, result.polynomial_interval = (
            install_polynomial_interval_capabilities(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                ctx.verification,
                ctx.checkers,
                authorize_checker=authorize,
            )
        )
        for interval_adapter in interval_adapters:
            if interval_adapter is not None:
                register(interval_adapter)

        positivity_adapters, result.polynomial_positivity = (
            install_polynomial_positivity_capabilities(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                ctx.verification,
                ctx.checkers,
                authorize_checker=authorize,
            )
        )
        for positivity_adapter in positivity_adapters:
            if positivity_adapter is not None:
                register(positivity_adapter)

        lean_adapters, result.lean_statement = install_lean_statement_capabilities(
            ctx.store,
            ctx.schemas,
            ctx.artifacts,
        )
        for lean_statement_adapter in lean_adapters:
            register(lean_statement_adapter)

    def _install_authorized_references(
        self,
        ctx: InstallationContext,
        application: ApplicationServices,
        result: PortfolioInstallation,
        register: CapabilityRegistrar,
    ) -> None:
        result.references = application.reference_installer.install_all()
        result.polytope_checkers = (
            application.reference_installer.install_polytope_checkers(
                claim_schema_uri=application.polytope.claim_schema_uri,
                semantics_uri=application.polytope.semantics_uri,
                point_schema_uri=application.polytope.point_schema_uri,
            )
        )
        result.lean_checkers = application.reference_installer.install_lean_checkers()
        profiles = {
            environment.value: {
                "semantics_uri": installation.semantics_uri,
                "import_name": installation.import_name,
                "mathlib_commit": installation.mathlib_commit,
                "allowed_axioms": list(installation.allowed_axioms),
                "checker_timeout_seconds": installation.checker_timeout_seconds,
            }
            for environment, installation in sorted(
                result.lean_checkers.items(),
                key=lambda item: item[0].value,
            )
        }
        runtime = lean_provider_runtime(
            profiles=profiles,
            checker_ids=tuple(
                installation.checker_id
                for _, installation in sorted(
                    result.lean_checkers.items(),
                    key=lambda item: item[0].value,
                )
            ),
        )
        result.lean_runtime = runtime
        if runtime.availability is not CapabilityProviderAvailability.AVAILABLE:
            _LOGGER.warning(
                "lean.check is not installed: %s",
                runtime.diagnostic,
            )
            return
        try:
            result.lean_declarations = installed_lean_declaration_service(runtime)
        except (OSError, RuntimeError) as exc:
            _LOGGER.warning(
                "Lean declaration discovery is not installed: %s",
                exc,
            )
        self._install_lean_declaration_adapters(ctx, result, register, runtime)
        result.lean = LeanService(
            ctx.store,
            ctx.artifacts,
            ctx.verification,
            result.lean_checkers,
        )
        register(LeanCheckAdapter(result.lean, runtime))
        lean_exploration_adapters, result.lean_exploration = (
            install_lean_exploration_capabilities(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                result.lean_checkers,
                runtime,
            )
        )
        for lean_exploration_adapter in lean_exploration_adapters:
            register(lean_exploration_adapter)
        self._install_lean_proof_edit(ctx, result, register, runtime)

    def _install_lean_declaration_adapters(
        self,
        ctx: InstallationContext,
        result: PortfolioInstallation,
        register: CapabilityRegistrar,
        runtime: CapabilityProviderRuntime,
    ) -> None:
        if result.lean_declarations is None:
            return
        register(LeanDeclarationSearchAdapter(result.lean_declarations, runtime))
        register(
            LeanDependencyGraphAdapter(
                result.lean_declarations,
                runtime,
                ctx.artifacts,
                semantics_uri=ctx.store.register_descriptor(
                    kind="semantics",
                    name="jacobian.lean4-declaration-dependencies",
                    version="1",
                    definition={
                        "description": (
                            "bounded constant dependencies extracted from elaborated "
                            "Lean declaration types and values"
                        ),
                        "provider_digest": runtime.digest,
                        "dependency_api": "Lean.Expr.getUsedConstantsAsSet",
                        "verification": "computed metadata; no theorem verification",
                    },
                ),
                dependency_graph_schema_uri=ctx.schemas.register(
                    name="jacobian.lean4-dependency-graph",
                    version="1",
                    schema=LeanDependencyGraphArtifact.model_json_schema(),
                ),
            )
        )
        register(LeanDeclarationInspectAdapter(result.lean_declarations, runtime))

    def _install_lean_proof_edit(
        self,
        ctx: InstallationContext,
        result: PortfolioInstallation,
        register: CapabilityRegistrar,
        runtime: CapabilityProviderRuntime,
    ) -> None:
        if result.lean is None or result.lean_runtime is None:
            return
        adapter, result.lean_proof_edit = install_lean_proof_edit_capability(
            ctx.store,
            ctx.schemas,
            ctx.artifacts,
            result.lean,
            runtime,
        )
        register(adapter)

    def _load_entrypoint_adapter(
        self,
        entrypoint: str,
        application: ApplicationServices,
    ) -> CapabilityAdapter:
        """Load one operator-approved ``factory(application)`` adapter entrypoint.

        This mirrors ``jacobian.capabilities.load_capability_adapter`` but
        passes ``ApplicationServices`` instead of ``JacobianRuntime``, so the
        assembler never imports or accepts the runtime.
        """

        if not _ENTRYPOINT_PATTERN.fullmatch(entrypoint):
            raise CapabilityError("capability adapter entrypoint has an invalid format")
        module_name, attribute_name = entrypoint.split(_ENTRYPOINT_SEPARATOR, 1)
        try:
            module = importlib.import_module(module_name)
            factory = getattr(module, attribute_name)
            adapter = factory(application)
            descriptor = adapter.descriptor
            invoke = adapter.invoke
        except _ENTRYPOINT_ERRORS as exc:
            raise CapabilityError(
                f"cannot load capability adapter entrypoint: {entrypoint}"
            ) from exc
        if not isinstance(descriptor, CapabilityDescriptor):
            raise CapabilityError("capability adapter does not implement the protocol")
        if not callable(invoke):
            raise CapabilityError("capability adapter does not implement the protocol")
        return cast(CapabilityAdapter, adapter)
