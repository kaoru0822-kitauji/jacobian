from __future__ import annotations

from jacobian.exact_domain_checkers import install_exact_domain_verification
from jacobian.portfolio.builtin import build_builtin_portfolio
from jacobian.runtime.model import JacobianRuntime


def _bundles(
    runtime: JacobianRuntime, *domain_ids: str
) -> dict[str, tuple[object, object]]:
    portfolio = build_builtin_portfolio()
    return {
        domain_id: (
            portfolio.bundle_for(domain_id),
            runtime.portfolio.domain_bundles[domain_id],
        )
        for domain_id in domain_ids
    }


def _install_verification(
    fresh_complete_runtime: JacobianRuntime, *, authorize: bool
) -> tuple[object, ...]:
    adapters, _ = install_exact_domain_verification(
        fresh_complete_runtime.core.store,
        fresh_complete_runtime.core.schemas,
        fresh_complete_runtime.core.artifacts,
        fresh_complete_runtime.services.verification,
        fresh_complete_runtime.core.checkers,
        bundles=_bundles(fresh_complete_runtime, "polynomial", "matrix", "probability"),
        authorize=authorize,
    )
    for adapter in adapters:
        fresh_complete_runtime.core.capabilities.register(adapter)
    return adapters


def test_probability_verification_installs_without_polynomial_or_matrix_bundles(
    fresh_complete_runtime,
) -> None:
    adapters, installation = install_exact_domain_verification(
        fresh_complete_runtime.core.store,
        fresh_complete_runtime.core.schemas,
        fresh_complete_runtime.core.artifacts,
        fresh_complete_runtime.services.verification,
        fresh_complete_runtime.core.checkers,
        bundles=_bundles(fresh_complete_runtime, "probability"),
        authorize=True,
    )

    assert [adapter.descriptor.capability_id for adapter in adapters] == [
        "probability.result.verify"
    ]
    assert any(installation.checker_ids.values())


def test_operator_can_leave_exact_result_verification_unavailable(
    fresh_complete_runtime,
) -> None:

    adapters = _install_verification(fresh_complete_runtime, authorize=False)

    assert adapters == ()
    assert {"polynomial.result.verify", "matrix.result.verify"}.isdisjoint(
        {
            descriptor.capability_id
            for descriptor in fresh_complete_runtime.core.capabilities.catalog().capabilities
        }
    )
