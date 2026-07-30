"""Behavioral tests for the explicit typed portfolio plan."""

from __future__ import annotations

import pytest

from jacobian.domains.builtins import build_builtin_domain_bundles
from jacobian.operations import DomainBundle
from jacobian.portfolio import PortfolioPlan, build_builtin_portfolio


def test_builtin_portfolio_is_an_explicit_plan_of_domain_bundles() -> None:
    plan = build_builtin_portfolio()

    assert isinstance(plan, PortfolioPlan)
    assert all(isinstance(bundle, DomainBundle) for bundle in plan.domain_bundles)
    # The plan is a literal ordered tuple, not discovered or registered.
    assert plan.domain_bundles == build_builtin_domain_bundles()
    assert plan.domain_ids == tuple(
        bundle.domain_id for bundle in build_builtin_domain_bundles()
    )


def test_validate_accepts_the_builtin_plan() -> None:
    # Must not raise.
    build_builtin_portfolio().validate()
    assert build_builtin_portfolio().domain_ids


def test_bundle_for_returns_the_declared_bundle_or_none() -> None:
    plan = build_builtin_portfolio()
    arithmetic = plan.bundle_for("arithmetic")
    assert isinstance(arithmetic, DomainBundle)
    assert arithmetic.domain_id == "arithmetic"
    assert plan.bundle_for("absent.domain") is None


def test_validate_rejects_duplicate_domain_bundles() -> None:
    bundle = build_builtin_domain_bundles()[0]
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
