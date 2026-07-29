"""Provider readiness access for provider-owned boundary fixtures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderReadiness:
    """The complete production readiness result for one named provider."""

    name: str
    available: bool
    diagnostic: str | None


PINNED_MATHLIB_RUNTIME_UNAVAILABLE_REASON = (
    "the pinned Lean and Mathlib runtime is unavailable"
)


def pinned_mathlib_runtime_available() -> bool:
    """Return whether the production pinned Lean/Mathlib probe succeeds.

    The implementation is imported lazily so this support module remains safe
    during collection of unit and component tests.
    """

    from jacobian.provider_runtime import lean_provider_runtime

    runtime = lean_provider_runtime(
        profiles={"mathlib": {"mathlib_commit": "pinned"}},
        checker_ids=(),
    )
    return runtime.availability.value == "available"


def provider_readiness(name: str) -> ProviderReadiness:
    """Resolve one provider through the production readiness probe.

    The resolver is imported lazily so merely collecting unit/component tests
    never imports optional provider implementations.
    """

    from jacobian.portfolio.provider_resolution import ProviderAvailabilityResolver

    plan = ProviderAvailabilityResolver().resolve()
    try:
        runtime = getattr(plan, name)
    except AttributeError as exc:
        raise ValueError(f"unknown provider readiness name: {name}") from exc
    return ProviderReadiness(
        name=name,
        available=runtime.availability.value == "available",
        diagnostic=runtime.diagnostic,
    )


def external_sat_toolchain_available() -> bool:
    """Return whether the pinned CaDiCaL and DRAT-trim pair is usable.

    A binary on ``PATH`` is not sufficient for these tests: the production
    probes also validate version, provenance, and the checker health command.
    """

    from jacobian.provider_runtime import (
        cadical_provider_runtime,
        drat_trim_provider_runtime,
    )

    return all(
        runtime.availability.value == "available"
        for runtime in (
            cadical_provider_runtime(),
            drat_trim_provider_runtime(),
        )
    )


def cadical_runtime_available() -> bool:
    """Return whether the pinned CaDiCaL executable passes its readiness probe."""

    from jacobian.provider_runtime import cadical_provider_runtime

    return cadical_provider_runtime().availability.value == "available"


def drat_trim_runtime_available() -> bool:
    """Return whether the pinned DRAT-trim checker passes readiness."""

    from jacobian.provider_runtime import drat_trim_provider_runtime

    return drat_trim_provider_runtime().availability.value == "available"
