"""Feature flag infrastructure for controlled rollout of experimental capabilities.

Feature flags enable safe introduction of new search strategies, checker
implementations, and plugin features behind toggles.  Flags are resolved at
process start from environment variables, ensuring consistent behaviour
across a single kernel session.

Environment variables follow the pattern ``JACOBIAN_FEATURE_<NAME>`` where
``<NAME>`` is the uppercase flag identifier.  Accepted values: ``1``, ``true``,
``on`` (case-insensitive) enable the flag; anything else leaves it disabled.
"""

from __future__ import annotations

import os
from typing import ClassVar

_TRUTHY = frozenset({"1", "true", "on"})


class FeatureFlags:
    """Namespace for kernel feature flags, resolved once from the environment."""

    # -- Search & evaluation --------------------------------------------------
    parallel_search: ClassVar[bool] = False
    """Run candidate search across multiple workers (experimental scheduler)."""

    exhaustive_enumeration: ClassVar[bool] = False
    """Permit complete finite-domain enumeration for bounded claims."""

    # -- Checkers -------------------------------------------------------------
    pluggable_checkers: ClassVar[bool] = True
    """Allow third-party checker plugins to participate in verification."""

    checker_concurrency: ClassVar[bool] = False
    """Run independent checker processes concurrently."""

    # -- Shrinking ------------------------------------------------------------
    adaptive_shrinking: ClassVar[bool] = False
    """Use heuristic-driven shrink prioritisation instead of round-robin."""

    # -- Observability --------------------------------------------------------
    structured_tracing: ClassVar[bool] = False
    """Emit structured execution traces for debugging / agent inspection."""

    @classmethod
    def is_enabled(cls, name: str) -> bool:
        """Return ``True`` when the named feature flag is active."""
        attr = getattr(cls, name, None)
        if attr is None:
            raise KeyError(f"Unknown feature flag: {name}")
        return bool(attr)

    @classmethod
    def snapshot(cls) -> dict[str, bool]:
        """Return a dict of all feature flags and their current values."""
        return {
            k: bool(v)
            for k, v in vars(cls).items()
            if not k.startswith("_") and isinstance(v, bool)
        }


def _resolve_from_env() -> None:
    prefix = "JACOBIAN_FEATURE_"
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        flag_name = key[len(prefix) :].lower()
        if hasattr(FeatureFlags, flag_name):
            setattr(FeatureFlags, flag_name, value.lower() in _TRUTHY)


_resolve_from_env()
