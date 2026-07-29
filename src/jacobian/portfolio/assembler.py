"""Ordered assembly of the explicit built-in mathematical portfolio."""

from __future__ import annotations

from dataclasses import dataclass

from jacobian.installation.context import InstallationContext
from jacobian.portfolio.core_installation import CoreApplicationInstaller
from jacobian.portfolio.foundation_installation import FoundationInstaller
from jacobian.portfolio.provider_resolution import ProviderAvailabilityResolver
from jacobian.portfolio.reference_installation import ReferenceLeanInstaller
from jacobian.portfolio.resource_installation import ResourceCapabilityInstaller
from jacobian.portfolio.result import PortfolioInstallation
from jacobian.runtime.services import ApplicationServices


@dataclass(slots=True)
class PortfolioAssembler:
    """Coordinate the explicit portfolio installation phases."""

    context: InstallationContext

    def install(
        self,
        application: ApplicationServices,
        *,
        capability_adapter_entrypoints: tuple[str, ...] = (),
    ) -> PortfolioInstallation:
        """Install the complete portfolio in its declared phase order."""

        result = PortfolioInstallation()
        resolver = ProviderAvailabilityResolver()
        runtimes = resolver.resolve()

        FoundationInstaller(self.context).install(
            application.core,
            result,
            runtimes,
        )
        CoreApplicationInstaller(self.context).install(
            application,
            result,
        )
        ResourceCapabilityInstaller(self.context).install(result)
        ReferenceLeanInstaller(self.context, resolver).install(
            application,
            result,
            capability_adapter_entrypoints=capability_adapter_entrypoints,
        )
        return result
