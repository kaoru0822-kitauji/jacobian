"""Cheap provider metadata inspection without importing implementations.

These helpers read installed distribution metadata through ``importlib.metadata``
only. They never import the provider package itself, so a missing or heavy
optional dependency cannot affect runtime startup or capability discovery.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, distribution, version


@dataclass(frozen=True, slots=True)
class DistributionSummary:
    """Typed installed-distribution metadata, without importing the package."""

    name: str
    version: str


def distribution_version(distribution_name: str) -> str | None:
    """Return installed distribution metadata without importing its package."""

    try:
        return version(distribution_name)
    except PackageNotFoundError:
        return None


def distribution_summary(distribution_name: str) -> DistributionSummary | None:
    """Return a typed summary of an installed distribution, or ``None``.

    The summary is read from distribution metadata only; the provider package
    is never imported. ``name`` falls back to the requested lookup name when
    the recorded ``Name`` header is missing or empty.
    """

    try:
        dist = distribution(distribution_name)
    except PackageNotFoundError:
        return None
    recorded_name = dist.metadata["Name"]
    return DistributionSummary(
        name=recorded_name or distribution_name,
        version=dist.version,
    )
