"""Installation of solver, linear, and normalization foundations.

This phase installs built-in adapters and checkers through one narrow
infrastructure context plus the core service graph.
It performs no discovery, registration, ranking, or verification authorization
beyond what the individual installers do.

This phase never imports or accepts ``JacobianRuntime`` and never creates a
facade. It consumes the explicit provider-runtime plan.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from jacobian.cadical import install_cadical_capabilities
from jacobian.contracts.capabilities import (
    CapabilityProviderAvailability,
    CapabilityProviderRuntime,
)
from jacobian.cvc5 import install_cvc5_capability
from jacobian.flint_hnf import install_python_flint_hnf_capability
from jacobian.flint_linear import (
    install_python_flint_inconsistency_capability,
    install_python_flint_linear_capability,
)
from jacobian.installation.context import InstallationContext
from jacobian.linear_capabilities import (
    install_linear_rational_inconsistency_checker,
    install_linear_rational_solution_checker,
)
from jacobian.matrix_normal_form_capabilities import (
    install_matrix_normal_form_checker,
)
from jacobian.polynomial_expression_capabilities import (
    install_polynomial_expression_checker,
)
from jacobian.portfolio.provider_resolution import ProviderRuntimePlan
from jacobian.portfolio.result import PortfolioInstallation
from jacobian.runtime.services import CoreServices
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

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FoundationInstaller:
    """Install foundational checkers and optional-provider adapters."""

    context: InstallationContext

    def install(
        self,
        core: CoreServices,
        result: PortfolioInstallation,
        runtimes: ProviderRuntimePlan,
    ) -> None:
        """Install solver, linear, and normalization foundations."""

        ctx = self.context
        self.context.register_capability(SatCnfMaterializationAdapter(core.sat))
        sat_assignment_adapter, result.sat_assignment_checker = (
            install_sat_assignment_checker(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                core.sat,
                ctx.verification,
                ctx.checkers,
                authorize_checker=ctx.authorizes_bundled_checkers,
            )
        )
        if sat_assignment_adapter is not None:
            self.context.register_capability(sat_assignment_adapter)

        result.drat_trim_runtime = runtimes.drat_trim
        proof_adapter, result.sat_unsat_proof_checker = install_sat_unsat_proof_checker(
            ctx.store,
            ctx.schemas,
            ctx.artifacts,
            core.sat,
            ctx.verification,
            ctx.checkers,
            result.drat_trim_runtime,
            authorize_checker=ctx.authorizes_bundled_checkers,
        )
        if proof_adapter is not None:
            self.context.register_capability(proof_adapter)

        lrat_adapter, result.sat_lrat = install_sat_lrat_verifier(
            ctx.store,
            ctx.schemas,
            ctx.artifacts,
            core.sat,
            ctx.verification,
            ctx.checkers,
            authorize_checker=ctx.authorizes_bundled_checkers,
        )
        if lrat_adapter is not None:
            self.context.register_capability(lrat_adapter)

        result.carcara_runtime = runtimes.carcara
        smt_proof_adapter, result.smt_unsat_proof_checker = (
            install_smt_unsat_proof_checker(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                core.smt,
                ctx.verification,
                ctx.checkers,
                result.carcara_runtime,
                authorize_checker=ctx.authorizes_bundled_checkers,
            )
        )
        if smt_proof_adapter is not None:
            self.context.register_capability(smt_proof_adapter)

        linear_adapter, result.linear_solution_checker = (
            install_linear_rational_solution_checker(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                core.linear,
                ctx.verification,
                ctx.checkers,
                authorize_checker=ctx.authorizes_bundled_checkers,
            )
        )
        if linear_adapter is not None:
            self.context.register_capability(linear_adapter)

        inconsistency_adapter, result.linear_inconsistency_checker = (
            install_linear_rational_inconsistency_checker(
                ctx.store,
                ctx.schemas,
                ctx.artifacts,
                core.linear,
                ctx.verification,
                ctx.checkers,
                authorize_checker=ctx.authorizes_bundled_checkers,
            )
        )
        if inconsistency_adapter is not None:
            self.context.register_capability(inconsistency_adapter)

        self._install_python_flint_capabilities(core, result, runtimes.python_flint)
        self._install_matrix_normal_form_capabilities(
            core,
            result,
            runtimes.python_flint_hnf,
        )
        self._install_polynomial_expression_capabilities(
            core,
            result,
            runtimes.sympy_polynomial_normalization,
        )
        self.install_optional_provider_components(core, result, runtimes)

    def install_optional_provider_components(
        self,
        core: CoreServices,
        result: PortfolioInstallation,
        runtimes: ProviderRuntimePlan,
    ) -> None:
        """Install capabilities backed by declared optional solver providers."""

        result.cadical_runtime = runtimes.cadical
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
                    self.context.register_capability(adapter)

        result.cvc5_runtime = runtimes.cvc5
        if result.cvc5_runtime.availability is CapabilityProviderAvailability.AVAILABLE:
            try:
                adapter = install_cvc5_capability(core.smt, result.cvc5_runtime)
            except OSError as exc:
                _LOGGER.warning("cvc5 SMT proof exploration is not installed: %s", exc)
            else:
                self.context.register_capability(adapter)

    # ------------------------------------------------------------------
    # Private installation helpers
    # ------------------------------------------------------------------

    def _install_python_flint_capabilities(
        self,
        core: CoreServices,
        result: PortfolioInstallation,
        runtime: CapabilityProviderRuntime,
    ) -> None:
        """Install exact rational linear producers when the pin is available."""

        result.python_flint_runtime = runtime
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
            self.context.register_capability(solution_adapter)
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
            self.context.register_capability(inconsistency_adapter)

    def _install_matrix_normal_form_capabilities(
        self,
        core: CoreServices,
        result: PortfolioInstallation,
        runtime: CapabilityProviderRuntime,
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
                authorize_checker=ctx.authorizes_bundled_checkers,
            )
        )
        if verification_adapter is not None:
            self.context.register_capability(verification_adapter)

        result.python_flint_hnf_runtime = runtime
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
            self.context.register_capability(adapter)

    def _install_polynomial_expression_capabilities(
        self,
        core: CoreServices,
        result: PortfolioInstallation,
        runtime: CapabilityProviderRuntime,
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
                authorize_checker=ctx.authorizes_bundled_checkers,
            )
        )
        if verification_adapter is not None:
            self.context.register_capability(verification_adapter)

        result.sympy_polynomial_normalization_runtime = runtime
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
            self.context.register_capability(adapter)
