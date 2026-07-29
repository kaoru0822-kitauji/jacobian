from __future__ import annotations

from jacobian.exact_domain_checkers import install_exact_domain_verification
from jacobian.runtime.model import JacobianRuntime


def _install_verification(
    fresh_complete_runtime: JacobianRuntime, *, authorize: bool
) -> tuple[object, ...]:
    adapters, _ = install_exact_domain_verification(
        fresh_complete_runtime.core.store,
        fresh_complete_runtime.core.schemas,
        fresh_complete_runtime.core.artifacts,
        fresh_complete_runtime.services.verification,
        fresh_complete_runtime.core.checkers,
        polynomial=fresh_complete_runtime.portfolio.domain_bundles["polynomial"],
        matrix=fresh_complete_runtime.portfolio.domain_bundles["matrix"],
        probability=fresh_complete_runtime.portfolio.domain_bundles.get("probability"),
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
        probability=fresh_complete_runtime.portfolio.domain_bundles["probability"],
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
