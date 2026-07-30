"""Direct tests for the provider-availability resolution phase."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from jacobian.contracts.capabilities import CapabilityProviderRuntime
from jacobian.portfolio import provider_resolution
from jacobian.portfolio.provider_resolution import ProviderAvailabilityResolver
from jacobian.provider_runtime import known_provider_runtime


def test_resolve_builds_one_typed_plan_from_each_declared_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def probe(name: str) -> Callable[[], CapabilityProviderRuntime]:
        def resolve() -> CapabilityProviderRuntime:
            calls.append(name)
            return known_provider_runtime(name)

        return resolve

    names = (
        "cadical",
        "carcara",
        "cvc5",
        "drat_trim",
        "python_flint",
        "python_flint_hnf",
        "sympy_polynomial_normalization",
    )
    for name in names:
        monkeypatch.setattr(
            provider_resolution,
            f"{name}_provider_runtime",
            probe(name),
        )

    plan = ProviderAvailabilityResolver().resolve()

    assert calls == list(names)
    assert tuple(getattr(plan, name).provider for name in names) == names


def test_lean_resolution_preserves_installed_checker_profile_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def resolve_lean(
        *,
        profiles: object,
        checker_ids: tuple[str, ...],
    ) -> CapabilityProviderRuntime:
        observed["profiles"] = profiles
        observed["checker_ids"] = checker_ids
        return known_provider_runtime("lean")

    monkeypatch.setattr(provider_resolution, "lean_provider_runtime", resolve_lean)
    profiles = {"mathlib": {"semantics_uri": "semantics://lean"}}

    runtime = ProviderAvailabilityResolver().resolve_lean(
        profiles=profiles,
        checker_ids=("lean.mathlib",),
    )

    assert runtime.provider == "lean"
    assert observed == {
        "profiles": profiles,
        "checker_ids": ("lean.mathlib",),
    }


def test_lean_frontend_resolution_uses_dedicated_health_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = known_provider_runtime("lean-frontend")
    monkeypatch.setattr(
        provider_resolution,
        "lean_frontend_provider_runtime",
        lambda: expected,
    )

    runtime = ProviderAvailabilityResolver().resolve_lean_frontend()

    assert runtime is expected
