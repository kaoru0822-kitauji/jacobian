"""Behavioral tests for the explicit typed portfolio plan."""

from __future__ import annotations

import pytest

from jacobian.domains.builtins import BUILTIN_DOMAIN_BUNDLES
from jacobian.operations import DomainBundle
from jacobian.portfolio import BUILTIN_PORTFOLIO, PortfolioPlan


def test_builtin_portfolio_is_an_explicit_plan_of_domain_bundles() -> None:
    plan = BUILTIN_PORTFOLIO

    assert isinstance(plan, PortfolioPlan)
    assert all(isinstance(bundle, DomainBundle) for bundle in plan.domain_bundles)
    # The plan is a literal ordered tuple, not discovered or registered.
    assert plan.domain_bundles == BUILTIN_DOMAIN_BUNDLES
    assert plan.domain_ids == tuple(
        bundle.domain_id for bundle in BUILTIN_DOMAIN_BUNDLES
    )


def test_validate_accepts_the_builtin_plan() -> None:
    # Must not raise.
    BUILTIN_PORTFOLIO.validate()
    assert BUILTIN_PORTFOLIO.domain_ids


def test_bundle_for_returns_the_declared_bundle_or_none() -> None:
    plan = BUILTIN_PORTFOLIO
    arithmetic = plan.bundle_for("arithmetic")
    assert isinstance(arithmetic, DomainBundle)
    assert arithmetic.domain_id == "arithmetic"
    assert plan.bundle_for("absent.domain") is None


def test_validate_rejects_duplicate_domain_bundles() -> None:
    bundle = BUILTIN_DOMAIN_BUNDLES[0]
    plan = PortfolioPlan(domain_bundles=(bundle, bundle))

    with pytest.raises(ValueError, match="duplicate domain bundles"):
        plan.validate()


def test_validate_rejects_non_domain_bundle_entries() -> None:
    impostor = object()
    plan = PortfolioPlan(domain_bundles=(impostor,))  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="DomainBundle instances"):
        plan.validate()


def test_empty_plan_validates_and_exposes_no_domains() -> None:
    plan = PortfolioPlan(domain_bundles=())

    plan.validate()
    assert plan.domain_bundles == ()
    assert plan.domain_ids == ()
    assert plan.bundle_for("anything") is None
