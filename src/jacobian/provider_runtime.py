"""Fail-closed runtime identity probes for capability providers."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import sysconfig
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import Any

from jacobian.contracts.capabilities import (
    CapabilityInstallTier,
    CapabilityProviderAvailability,
    CapabilityProviderDigestKind,
    CapabilityProviderRuntime,
)
from jacobian.implementation import ImplementationError, package_source_digest


class ProviderRuntimeError(RuntimeError):
    """Raised when a required provider identity cannot be inspected safely."""


@cache
def _platform_tag() -> str:
    return sysconfig.get_platform()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def _distribution_record_digest(
    distribution: importlib.metadata.Distribution,
) -> str:
    rows: list[str] = []
    hashed = 0
    for package_path in sorted(distribution.files or (), key=str):
        file_hash = package_path.hash
        if file_hash is None:
            hash_value = "-"
        else:
            hash_value = f"{file_hash.mode}:{file_hash.value}"
            hashed += 1
        size = "-" if package_path.size is None else str(package_path.size)
        rows.append(f"{package_path}\0{hash_value}\0{size}\n")
    if not rows or not hashed:
        raise ProviderRuntimeError(
            "the installed Python distribution has no hashed RECORD manifest"
        )
    digest = hashlib.sha256("".join(rows).encode()).hexdigest()
    return f"sha256:{digest}"


def _license_files(
    distribution: importlib.metadata.Distribution,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            str(package_path).replace("\\", "/")
            for package_path in distribution.files or ()
            if "license" in package_path.name.lower()
        )
    )


@cache
def _jacobian_identity() -> tuple[str, str, tuple[str, ...]]:
    try:
        distribution = importlib.metadata.distribution("jacobian")
        digest = package_source_digest("jacobian.capabilities:CapabilityService")
    except (importlib.metadata.PackageNotFoundError, ImplementationError) as exc:
        raise ProviderRuntimeError(
            "the Jacobian source runtime could not be identified"
        ) from exc
    return distribution.version, digest, _license_files(distribution)


@cache
def _python_distribution_identity(
    distribution_name: str,
    import_name: str,
    required_attributes: tuple[str, ...],
) -> tuple[str, str, tuple[str, ...]]:
    try:
        module = importlib.import_module(import_name)
        for attribute in required_attributes:
            getattr(module, attribute)
        distribution = importlib.metadata.distribution(distribution_name)
        digest = _distribution_record_digest(distribution)
    except (
        AttributeError,
        ImportError,
        importlib.metadata.PackageNotFoundError,
        ProviderRuntimeError,
    ) as exc:
        raise ProviderRuntimeError(
            f"the {distribution_name} provider is not installed and healthy"
        ) from exc
    return distribution.version, digest, _license_files(distribution)


def _unavailable_runtime(
    *,
    provider: str,
    install_tier: CapabilityInstallTier,
    license_id: str,
    diagnostic: str,
) -> CapabilityProviderRuntime:
    return CapabilityProviderRuntime(
        provider=provider,
        availability=CapabilityProviderAvailability.UNAVAILABLE,
        platform=_platform_tag(),
        install_tier=install_tier,
        license_id=license_id,
        diagnostic=diagnostic,
    )


def jacobian_provider_runtime(
    provider: str,
    *,
    features: tuple[str, ...] = (),
    checker_ids: tuple[str, ...] = (),
    configuration: Mapping[str, Any] | None = None,
) -> CapabilityProviderRuntime:
    """Identify a source-backed provider implemented inside Jacobian."""

    try:
        version, digest, license_files = _jacobian_identity()
    except ProviderRuntimeError:
        return _unavailable_runtime(
            provider=provider,
            install_tier=CapabilityInstallTier.T0,
            license_id="MIT",
            diagnostic="The Jacobian source runtime could not be identified.",
        )
    return CapabilityProviderRuntime(
        provider=provider,
        availability=CapabilityProviderAvailability.AVAILABLE,
        version=version,
        digest=digest,
        digest_kind=CapabilityProviderDigestKind.SOURCE_TREE,
        platform=_platform_tag(),
        install_tier=CapabilityInstallTier.T0,
        license_id="MIT",
        license_files=license_files,
        features=features,
        checker_ids=checker_ids,
        configuration=dict(configuration or {}),
    )


def source_provider_runtime(
    provider: str,
    *,
    version: str,
    entrypoint: str,
    install_tier: CapabilityInstallTier,
    license_id: str,
    license_files: tuple[str, ...] = (),
    features: tuple[str, ...] = (),
    checker_ids: tuple[str, ...] = (),
    configuration: Mapping[str, Any] | None = None,
) -> CapabilityProviderRuntime:
    """Identify an operator-installed source package without importing its code."""

    try:
        digest = package_source_digest(entrypoint)
    except ImplementationError:
        return _unavailable_runtime(
            provider=provider,
            install_tier=install_tier,
            license_id=license_id,
            diagnostic="The provider source package could not be identified.",
        )
    return CapabilityProviderRuntime(
        provider=provider,
        availability=CapabilityProviderAvailability.AVAILABLE,
        version=version,
        digest=digest,
        digest_kind=CapabilityProviderDigestKind.SOURCE_TREE,
        platform=_platform_tag(),
        install_tier=install_tier,
        license_id=license_id,
        license_files=license_files,
        features=features,
        checker_ids=checker_ids,
        configuration={
            "entrypoint": entrypoint,
            **dict(configuration or {}),
        },
    )


def python_distribution_provider_runtime(
    provider: str,
    *,
    distribution_name: str,
    import_name: str,
    required_attributes: tuple[str, ...],
    install_tier: CapabilityInstallTier,
    license_id: str,
    features: tuple[str, ...] = (),
    checker_ids: tuple[str, ...] = (),
    configuration: Mapping[str, Any] | None = None,
) -> CapabilityProviderRuntime:
    """Identify one installed Python distribution without trusting an import alone."""

    try:
        version, digest, license_files = _python_distribution_identity(
            distribution_name,
            import_name,
            required_attributes,
        )
    except ProviderRuntimeError:
        return _unavailable_runtime(
            provider=provider,
            install_tier=install_tier,
            license_id=license_id,
            diagnostic=(
                f"The {distribution_name} provider is not installed and healthy."
            ),
        )
    return CapabilityProviderRuntime(
        provider=provider,
        availability=CapabilityProviderAvailability.AVAILABLE,
        version=version,
        digest=digest,
        digest_kind=CapabilityProviderDigestKind.PYTHON_DISTRIBUTION_RECORD,
        platform=_platform_tag(),
        install_tier=install_tier,
        license_id=license_id,
        license_files=license_files,
        features=features,
        checker_ids=checker_ids,
        configuration={
            "distribution": distribution_name,
            **dict(configuration or {}),
        },
    )


def known_provider_runtime(
    provider: str,
    *,
    features: tuple[str, ...] = (),
    checker_ids: tuple[str, ...] = (),
    configuration: Mapping[str, Any] | None = None,
) -> CapabilityProviderRuntime:
    """Resolve runtime identity for a built-in provider family."""

    if provider == "jacobian.networkx":
        return python_distribution_provider_runtime(
            provider,
            distribution_name="networkx",
            import_name="networkx",
            required_attributes=("Graph", "graph_atlas_g"),
            install_tier=CapabilityInstallTier.T0,
            license_id="BSD-3-Clause",
            features=features,
            checker_ids=checker_ids,
            configuration=configuration,
        )
    if provider == "jacobian.sympy":
        return python_distribution_provider_runtime(
            provider,
            distribution_name="sympy",
            import_name="sympy",
            required_attributes=("Matrix", "Poly"),
            install_tier=CapabilityInstallTier.T0,
            license_id="BSD-3-Clause",
            features=features,
            checker_ids=checker_ids,
            configuration=configuration,
        )
    if provider == "jacobian.z3":
        return python_distribution_provider_runtime(
            provider,
            distribution_name="z3-solver",
            import_name="z3",
            required_attributes=("Real", "Solver"),
            install_tier=CapabilityInstallTier.T0,
            license_id="MIT",
            features=features,
            checker_ids=checker_ids,
            configuration=configuration,
        )
    return jacobian_provider_runtime(
        provider,
        features=features,
        checker_ids=checker_ids,
        configuration=configuration,
    )


def lean_provider_runtime(
    *,
    profiles: Mapping[str, Mapping[str, Any]],
    checker_ids: tuple[str, ...],
) -> CapabilityProviderRuntime:
    """Inspect the separately managed pinned Lean/Mathlib runtime."""

    from jacobian_checkers import lean4

    require_mathlib = any(
        profile.get("mathlib_commit") is not None for profile in profiles.values()
    )
    try:
        executable, _ = lean4.inspect_runtime(require_mathlib=require_mathlib)
        digest = _sha256_file(executable)
    except (OSError, RuntimeError):
        return _unavailable_runtime(
            provider="jacobian.lean4",
            install_tier=CapabilityInstallTier.T3,
            license_id="Apache-2.0",
            diagnostic=(
                f"The pinned Lean {lean4.LEAN_VERSION} runtime is unavailable."
            ),
        )
    return CapabilityProviderRuntime(
        provider="jacobian.lean4",
        availability=CapabilityProviderAvailability.AVAILABLE,
        version=lean4.LEAN_VERSION,
        digest=digest,
        digest_kind=CapabilityProviderDigestKind.EXECUTABLE,
        platform=_platform_tag(),
        install_tier=CapabilityInstallTier.T3,
        license_id="Apache-2.0",
        features=tuple(sorted(profiles)),
        checker_ids=checker_ids,
        configuration={"profiles": dict(profiles)},
    )
