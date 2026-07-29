"""Helpers for installing explicitly selected domain bundles in tests."""

from __future__ import annotations

from jacobian.operations import DomainBundle
from jacobian.portfolio.domain_installation import DomainBundleInstaller
from jacobian.portfolio.model import PortfolioPlan
from jacobian.portfolio.result import PortfolioInstallationResult
from tests.support.services import DomainTestServices


def install_domain_bundle(
    services: DomainTestServices,
    bundle: DomainBundle,
) -> PortfolioInstallationResult:
    """Install exactly ``bundle`` through the production domain installer."""

    return DomainBundleInstaller(services.installation).install(
        PortfolioPlan(domain_bundles=(bundle,))
    )
