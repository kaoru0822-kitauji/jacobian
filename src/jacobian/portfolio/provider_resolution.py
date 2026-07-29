"""Explicit resolution of optional provider runtime availability."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from jacobian.contracts.capabilities import CapabilityProviderRuntime
from jacobian.provider_runtime import (
    cadical_provider_runtime,
    carcara_provider_runtime,
    cvc5_provider_runtime,
    drat_trim_provider_runtime,
    lean_frontend_provider_runtime,
    lean_provider_runtime,
    python_flint_hnf_provider_runtime,
    python_flint_provider_runtime,
    sympy_polynomial_normalization_provider_runtime,
)


@dataclass(frozen=True, slots=True)
class ProviderRuntimePlan:
    """Resolved runtimes consumed by installation without repeating probes."""

    cadical: CapabilityProviderRuntime
    carcara: CapabilityProviderRuntime
    cvc5: CapabilityProviderRuntime
    drat_trim: CapabilityProviderRuntime
    python_flint: CapabilityProviderRuntime
    python_flint_hnf: CapabilityProviderRuntime
    sympy_polynomial_normalization: CapabilityProviderRuntime


@dataclass(frozen=True, slots=True)
class ProviderAvailabilityResolver:
    """Resolve provider availability before capability installation begins."""

    def resolve(self) -> ProviderRuntimePlan:
        return ProviderRuntimePlan(
            cadical=cadical_provider_runtime(),
            carcara=carcara_provider_runtime(),
            cvc5=cvc5_provider_runtime(),
            drat_trim=drat_trim_provider_runtime(),
            python_flint=python_flint_provider_runtime(),
            python_flint_hnf=python_flint_hnf_provider_runtime(),
            sympy_polynomial_normalization=(
                sympy_polynomial_normalization_provider_runtime()
            ),
        )

    def resolve_lean(
        self,
        *,
        profiles: Mapping[str, Mapping[str, object]],
        checker_ids: tuple[str, ...],
    ) -> CapabilityProviderRuntime:
        """Resolve Lean after authorized checker profiles have been installed."""

        return lean_provider_runtime(profiles=profiles, checker_ids=checker_ids)

    def resolve_lean_frontend(self) -> CapabilityProviderRuntime:
        """Resolve the pinned CORE Lean frontend before statement registration."""

        return lean_frontend_provider_runtime()
