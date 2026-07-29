"""Whole-portfolio installation coverage belongs to the integration lane."""

from jacobian.portfolio import BUILTIN_PORTFOLIO
from jacobian.portfolio.result import BundleInstallationStatus
from jacobian.runtime.model import JacobianRuntime


def test_builtin_portfolio_installs_cleanly(
    fresh_complete_runtime: JacobianRuntime,
) -> None:
    installation = fresh_complete_runtime.portfolio

    assert installation.portfolio_diagnostics == ()
    assert set(installation.domain_bundles) == set(BUILTIN_PORTFOLIO.domain_ids)
    assert all(
        outcome.status is BundleInstallationStatus.INSTALLED
        for outcome in installation.portfolio_outcomes
    )
    expected_capability_ids = {
        operation.capability_id
        for bundle in BUILTIN_PORTFOLIO.domain_bundles
        for operation in bundle.capabilities
    }
    installed_capability_ids = {
        descriptor.capability_id
        for descriptor in fresh_complete_runtime.core.capabilities.catalog().capabilities
    }
    assert expected_capability_ids <= installed_capability_ids
