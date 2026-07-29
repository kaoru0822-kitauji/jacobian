from __future__ import annotations

from pathlib import Path

import pytest

from jacobian.capabilities import CapabilityError
from jacobian.contracts.capabilities import (
    CapabilityAssurance,
    CapabilityAssuranceLevel,
    CapabilityDescriptor,
    CapabilityInstallTier,
    CapabilityMode,
    CapabilityProviderAvailability,
    CapabilityProviderDigestKind,
    CapabilityProviderRuntime,
    CapabilityRequest,
    CapabilityResult,
)
from jacobian.contracts.results import Execution, ExecutionStatus
from jacobian.domains.builtins import BUILTIN_DOMAIN_BUNDLES
from jacobian.domains.graph_optimization.bundle import GRAPH_OPTIMIZATION_BUNDLE
from jacobian.domains.graph_optimization.invariant_bundle import (
    GRAPH_INVARIANT_BUNDLE,
)
from jacobian.provider_measurements import _cold_install_spec
from jacobian.runtime import CheckerAuthorityMode, create_runtime


class UnavailableAdapter:
    descriptor = CapabilityDescriptor(
        capability_id="fixture.unavailable",
        version="1",
        title="Unavailable fixture",
        description="Exercise fail-closed provider registration.",
        provider="tests.unavailable",
        provider_runtime=CapabilityProviderRuntime(
            provider="tests.unavailable",
            availability=CapabilityProviderAvailability.UNAVAILABLE,
            platform="linux-x86_64",
            install_tier=CapabilityInstallTier.T2,
            license_id="MIT",
            diagnostic="The fixture executable is not installed.",
        ),
        modes=(CapabilityMode.EXPLORE,),
        input_schema={"type": "object"},
        output_schema={"type": "object"},
    )

    def invoke(self, request: CapabilityRequest) -> CapabilityResult:
        raise AssertionError(f"unavailable adapter invoked: {request.capability_id}")


def test_catalog_exposes_exact_runtime_identity_for_every_adapter(
    runtime,
) -> None:
    descriptors = {
        item.capability_id: item
        for item in runtime.core.capabilities.catalog().capabilities
    }

    assert descriptors
    assert all(
        item.provider_runtime.availability is CapabilityProviderAvailability.AVAILABLE
        for item in descriptors.values()
    )
    assert all(
        item.provider_runtime.digest is not None for item in descriptors.values()
    )
    assert descriptors["graph.compute.properties"].provider_runtime.provider == (
        "jacobian.networkx"
    )
    assert (
        descriptors["polynomial.map.compute_jacobian"].provider_runtime.provider
        == "jacobian.sympy"
    )
    assert (
        descriptors["universal_algebra.search.countermodel"].provider_runtime.provider
        == "jacobian.z3"
    )
    built_in_ids = {
        operation.capability_id
        for bundle in BUILTIN_DOMAIN_BUNDLES
        for operation in bundle.capabilities
    }
    assert built_in_ids <= descriptors.keys()
    assert set(runtime.portfolio.domain_bundles) == {
        bundle.domain_id for bundle in BUILTIN_DOMAIN_BUNDLES
    }
    assert {
        "matrix.integer.row_hermite_normal_form",
        "matrix.integer.smith_normal_form",
        "polynomial.rational.gcd.compute",
        "lean.proof.repair_once",
    }.isdisjoint(descriptors)


def test_unavailable_adapter_is_rejected_before_catalog_advertisement(
    runtime,
) -> None:

    with pytest.raises(CapabilityError, match="is unavailable"):
        runtime.core.capabilities.register(UnavailableAdapter())

    assert "fixture.unavailable" not in {
        item.capability_id for item in runtime.core.capabilities.catalog().capabilities
    }


def test_graph_domain_runtime_identities_bind_every_executed_backend() -> None:
    optimization_components = GRAPH_OPTIMIZATION_BUNDLE.provider_runtime.configuration[
        "components"
    ]
    invariant_components = GRAPH_INVARIANT_BUNDLE.provider_runtime.configuration[
        "components"
    ]

    assert {component["provider"] for component in optimization_components} == {
        "jacobian.networkx",
        "jacobian.sympy",
        "jacobian.z3",
    }
    assert {component["provider"] for component in invariant_components} == {
        "jacobian.networkx",
        "jacobian.sympy",
    }
    assert (
        GRAPH_OPTIMIZATION_BUNDLE.provider_runtime.digest_kind
        is CapabilityProviderDigestKind.COMPOSITE
    )
    assert (
        GRAPH_INVARIANT_BUNDLE.provider_runtime.digest_kind
        is CapabilityProviderDigestKind.COMPOSITE
    )


def test_unhealthy_optional_lean_runtime_is_absent_from_catalog(
    tmp_path: Path,
    initialized_runtime_store_with_references: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = initialized_runtime_store_with_references
    unavailable = CapabilityProviderRuntime(
        provider="jacobian.lean4",
        availability=CapabilityProviderAvailability.UNAVAILABLE,
        platform="linux-x86_64",
        install_tier=CapabilityInstallTier.T3,
        license_id="Apache-2.0",
        diagnostic="The pinned Lean runtime is unavailable.",
    )
    monkeypatch.setattr(
        "jacobian.portfolio.assembler.lean_provider_runtime",
        lambda **_kwargs: unavailable,
    )

    runtime = create_runtime(
        tmp_path, checker_authority=CheckerAuthorityMode.HYDRATE_EXISTING
    )

    assert runtime.portfolio.lean is None
    assert runtime.portfolio.lean_proof_edit is None
    capability_ids = {
        item.capability_id for item in runtime.core.capabilities.catalog().capabilities
    }
    assert {
        "lean.check",
        "lean.declaration.dependencies",
        "lean.declaration.inspect",
        "lean.declaration.search",
        "lean.proof_edit.validate",
    }.isdisjoint(capability_ids)


def test_invocation_binds_descriptor_runtime_to_result_provenance(
    runtime,
) -> None:
    descriptor = next(
        item
        for item in runtime.core.capabilities.catalog().capabilities
        if item.capability_id == "polynomial.map.evaluate"
    )
    # Invalid input is intentional: provenance must also survive failed execution.
    result = runtime.core.capabilities.invoke(
        CapabilityRequest(
            capability_id=descriptor.capability_id,
            mode=CapabilityMode.EXPLORE,
            input={},
        )
    )

    assert result.execution.status is ExecutionStatus.ERROR
    assert descriptor.provider_runtime is not None
    assert result.provider == descriptor.provider
    assert result.provider_digest == descriptor.provider_runtime.digest


def test_runtime_contract_accepts_a_bound_completed_result() -> None:
    runtime = CapabilityProviderRuntime(
        provider="tests.fixture",
        availability=CapabilityProviderAvailability.AVAILABLE,
        version="1",
        digest="sha256:" + "a" * 64,
        digest_kind=CapabilityProviderDigestKind.SOURCE_TREE,
        platform="any",
        install_tier=CapabilityInstallTier.T0,
        license_id="MIT",
    )
    result = CapabilityResult(
        capability_id="fixture.identity",
        capability_version="1",
        mode=CapabilityMode.EXPLORE,
        execution=Execution(status=ExecutionStatus.COMPLETED),
        assurance=CapabilityAssurance(
            level=CapabilityAssuranceLevel.COMPUTED,
            basis="fixture computation",
        ),
        provider=runtime.provider,
        provider_digest=runtime.digest,
    )

    assert result.provider == runtime.provider
    assert result.provider_digest == runtime.digest


def test_source_runtime_has_no_implicit_working_directory_install() -> None:
    runtime = CapabilityProviderRuntime(
        provider="tests.fixture",
        availability=CapabilityProviderAvailability.AVAILABLE,
        version="1",
        digest="sha256:" + "a" * 64,
        digest_kind=CapabilityProviderDigestKind.SOURCE_TREE,
        platform="any",
        install_tier=CapabilityInstallTier.T1,
        license_id="MIT",
    )

    assert _cold_install_spec(runtime) is None
