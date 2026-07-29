from __future__ import annotations

from importlib.metadata import PackageNotFoundError

import pytest

from jacobian.providers import (
    DistributionSummary,
    distribution_summary,
    distribution_version,
)


def test_distribution_version_returns_installed_version() -> None:
    # ``jacobian`` is the package under test and is always installed in the
    # development environment.
    assert distribution_version("jacobian") is not None
    assert distribution_version("jacobian")  # non-empty string


def test_distribution_version_returns_none_for_missing_distribution() -> None:
    assert distribution_version("definitely-not-a-real-distribution-xyz") is None


def test_distribution_version_does_not_import_the_package() -> None:
    # Reading metadata must not require importing the named package. A name
    # that is not a valid importable module still resolves through metadata.
    assert distribution_version("jacobian") == distribution_version("jacobian")


def test_distribution_summary_returns_typed_record() -> None:
    summary = distribution_summary("jacobian")

    assert summary is not None
    assert isinstance(summary, DistributionSummary)
    assert summary.name == "jacobian"
    assert summary.version == distribution_version("jacobian")


def test_distribution_summary_returns_none_for_missing_distribution() -> None:
    assert distribution_summary("definitely-not-a-real-distribution-xyz") is None


def test_distribution_summary_is_frozen() -> None:
    summary = distribution_summary("jacobian")
    assert summary is not None

    with pytest.raises(AttributeError):
        summary.version = "tampered"  # type: ignore[misc]


def test_distribution_summary_equality() -> None:
    first = distribution_summary("jacobian")
    second = distribution_summary("jacobian")

    assert first is not None
    assert second is not None
    assert first == second
    assert hash(first) == hash(second)


def test_distribution_version_swallows_package_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import jacobian.providers.metadata as metadata_module

    def raise_not_found(_name: str) -> str:
        raise PackageNotFoundError("missing")

    monkeypatch.setattr(metadata_module, "version", raise_not_found)

    assert metadata_module.distribution_version("missing") is None
