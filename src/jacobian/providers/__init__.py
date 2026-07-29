"""Provider inspection and lazy implementation loading.

This package provides two independent, composable primitives:

* :func:`distribution_version` and :func:`distribution_summary` read installed
  distribution metadata through ``importlib.metadata`` without ever importing
  the provider package, so a missing or heavy optional dependency cannot
  affect runtime startup.
* :class:`LazyLoader` defers importing or constructing a heavy optional
  implementation until first use, caches success and failure, owns the
  implementation lifecycle, and exposes a typed :class:`LoaderState`.

The package deliberately avoids registries, package discovery, import-time
registration, and compatibility shims. Each loader is an independent, owned
object; metadata helpers are pure functions.
"""

from __future__ import annotations

from jacobian.providers.loader import LazyLoader, LazyLoadError, LoaderState
from jacobian.providers.metadata import (
    DistributionSummary,
    distribution_summary,
    distribution_version,
)

__all__ = [
    "DistributionSummary",
    "LazyLoadError",
    "LazyLoader",
    "LoaderState",
    "distribution_summary",
    "distribution_version",
]
