from __future__ import annotations

import pytest
from pydantic import ValidationError

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
