from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import jacobian.provider_runtime as provider_runtime
from jacobian.contracts.capabilities import (
    CapabilityDescriptor,
    CapabilityInstallTier,
    CapabilityMode,
    CapabilityProviderAvailability,
    CapabilityProviderDigestKind,
    CapabilityProviderRuntime,
)
from jacobian.contracts.provider_measurements import (
    ProviderMeasurementSample,
    ProviderMeasurementStatus,
)
from jacobian.provider_runtime import (
    ProviderRuntimeError,
    composite_provider_runtime,
    exact_domain_checker_provider_runtime,
    require_provider_runtime_unchanged,
)


def _runtime(**updates: object) -> CapabilityProviderRuntime:
    values: dict[str, object] = {
        "provider": "tests.fixture",
        "availability": CapabilityProviderAvailability.AVAILABLE,
        "version": "1.2.3",
        "digest": "sha256:" + "a" * 64,
        "digest_kind": CapabilityProviderDigestKind.PYTHON_DISTRIBUTION_RECORD,
        "platform": "linux-x86_64",
        "install_tier": CapabilityInstallTier.T1,
        "license_id": "MIT",
        "license_files": ("fixture.dist-info/licenses/LICENSE",),
        "features": ("exact-arithmetic",),
        "checker_ids": ("checker://sha256/" + "b" * 64,),
    }
    values.update(updates)
    return CapabilityProviderRuntime(**values)


def test_available_provider_requires_exact_version_and_digest() -> None:
    with pytest.raises(
        ValidationError,
        match="available provider runtime requires version, digest, and digest kind",
    ):
        _runtime(version=None, digest=None, digest_kind=None)


def test_provider_metadata_rejects_duplicate_features_and_checker_ids() -> None:
    with pytest.raises(ValidationError, match="provider features must be unique"):
        _runtime(features=("exact-arithmetic", "exact-arithmetic"))
    checker_id = "checker://sha256/" + "b" * 64
    with pytest.raises(ValidationError, match="provider checker IDs must be unique"):
        _runtime(checker_ids=(checker_id, checker_id))


def test_unavailable_provider_requires_a_public_diagnostic() -> None:
    with pytest.raises(
        ValidationError,
        match="unavailable provider runtime requires a diagnostic",
    ):
        _runtime(
            availability=CapabilityProviderAvailability.UNAVAILABLE,
            version=None,
            digest=None,
            digest_kind=None,
        )


def test_descriptor_provider_must_match_runtime_identity() -> None:
    with pytest.raises(ValidationError, match="descriptor provider must match"):
        CapabilityDescriptor(
            capability_id="fixture.increment",
            version="1",
            title="Increment",
            description="Increment one integer.",
            provider="tests.other",
            provider_runtime=_runtime(),
            modes=(CapabilityMode.EXPLORE,),
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )


def test_composite_provider_binds_all_component_identities() -> None:
    first = _runtime(provider="tests.first", version="1")
    second = _runtime(
        provider="tests.second",
        version="2",
        digest="sha256:" + "c" * 64,
    )

    runtime = composite_provider_runtime(
        "tests.composite",
        components=(first, second),
        features=("two-backends",),
    )

    assert runtime.availability is CapabilityProviderAvailability.AVAILABLE
    assert runtime.digest_kind is CapabilityProviderDigestKind.COMPOSITE
    assert runtime.digest is not None
    assert tuple(
        component["provider"] for component in runtime.configuration["components"]
    ) == ("tests.first", "tests.second")
    changed = composite_provider_runtime(
        "tests.composite",
        components=(first, second.model_copy(update={"version": "3"})),
        features=("two-backends",),
    )
    assert changed.digest != runtime.digest


def test_composite_provider_fails_closed_when_one_component_is_unavailable() -> None:
    unavailable = _runtime(
        provider="tests.missing",
        availability=CapabilityProviderAvailability.UNAVAILABLE,
        version=None,
        digest=None,
        digest_kind=None,
        diagnostic="Missing fixture runtime.",
    )

    runtime = composite_provider_runtime(
        "tests.composite",
        components=(_runtime(provider="tests.present"), unavailable),
    )

    assert runtime.availability is CapabilityProviderAvailability.UNAVAILABLE
    assert runtime.digest is None
    assert runtime.diagnostic is not None
    assert "tests.missing" in runtime.diagnostic


def test_exact_checker_composite_runtime_is_remeasured_recursively() -> None:
    runtime = exact_domain_checker_provider_runtime(refresh=True)
    require_provider_runtime_unchanged(runtime)

    components = list(runtime.configuration["components"])
    flint = dict(components[1])
    flint["digest"] = "sha256:" + "0" * 64
    components[1] = flint
    changed = runtime.model_copy(
        update={
            "configuration": {
                **runtime.configuration,
                "components": components,
            }
        }
    )

    with pytest.raises(ProviderRuntimeError, match="identity changed"):
        require_provider_runtime_unchanged(changed)


def test_exact_checker_runtime_requires_rational_polynomial_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incomplete_flint = SimpleNamespace(
        __FLINT_VERSION__=provider_runtime.PYTHON_FLINT_HNF_FLINT_VERSION,
        fmpq=object(),
        fmpq_mat=object(),
        fmpz=object(),
        fmpz_mat=object(),
        fmpz_poly=object(),
    )
    monkeypatch.setattr(
        provider_runtime.importlib,
        "import_module",
        lambda _name: incomplete_flint,
    )

    runtime = provider_runtime.python_flint_exact_checker_provider_runtime(refresh=True)

    assert runtime.availability is CapabilityProviderAvailability.UNAVAILABLE
    assert runtime.digest is None


def test_exact_checker_runtime_rejects_different_linked_flint_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    available = provider_runtime.python_flint_exact_checker_provider_runtime()
    assert available.availability is CapabilityProviderAvailability.AVAILABLE
    monkeypatch.setattr(
        provider_runtime,
        "python_distribution_provider_runtime",
        lambda *_args, **_kwargs: available,
    )
    monkeypatch.setattr(
        provider_runtime.importlib,
        "import_module",
        lambda _name: SimpleNamespace(__FLINT_VERSION__="3.5.0"),
    )

    runtime = provider_runtime.python_flint_exact_checker_provider_runtime(refresh=True)

    assert runtime.availability is CapabilityProviderAvailability.UNAVAILABLE
    assert runtime.digest is None
    assert runtime.diagnostic is not None
    assert "linked FLINT library" in runtime.diagnostic


def test_measurement_status_cannot_hide_missing_elapsed_time() -> None:
    with pytest.raises(
        ValidationError,
        match="completed provider measurement requires elapsed seconds",
    ):
        ProviderMeasurementSample(status=ProviderMeasurementStatus.COMPLETED)

    with pytest.raises(
        ValidationError,
        match="incomplete provider measurement requires a detail",
    ):
        ProviderMeasurementSample(status=ProviderMeasurementStatus.SKIPPED)
