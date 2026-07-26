from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from jacobian.builtin_capabilities import (
    LeanDeclarationInspectAdapter,
    LeanDeclarationSearchAdapter,
)
from jacobian.capabilities import CapabilityInvocationError
from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityCompletenessStatus,
    CapabilityInstallTier,
    CapabilityMode,
    CapabilityProviderAvailability,
    CapabilityProviderDigestKind,
    CapabilityProviderRuntime,
    CapabilityRequest,
)
from jacobian.contracts.lean import LeanEnvironment
from jacobian.lean_declarations import (
    LeanDeclarationBackend,
    LeanDeclarationBackendError,
    LeanDeclarationService,
    LeanSubprocessDeclarationBackend,
)

_DIGEST = "sha256:" + "a" * 64
_RUNTIME = CapabilityProviderRuntime(
    provider="jacobian.lean4",
    availability=CapabilityProviderAvailability.AVAILABLE,
    version="4.31.0",
    digest="sha256:" + "b" * 64,
    digest_kind=CapabilityProviderDigestKind.EXECUTABLE,
    platform="test",
    install_tier=CapabilityInstallTier.T3,
    license_id="Apache-2.0",
    features=("CORE", "MATHLIB"),
)


@dataclass
class FakeBackend(LeanDeclarationBackend):
    response: dict[str, Any]
    calls: list[tuple[LeanEnvironment, dict[str, Any]]] = field(default_factory=list)

    def environment_digest(self, _environment: LeanEnvironment) -> str:
        return _DIGEST

    def query(
        self,
        environment: LeanEnvironment,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append((environment, payload))
        return self.response


class MissingDeclarationBackend:
    def environment_digest(self, _environment: LeanEnvironment) -> str:
        return _DIGEST

    def query(
        self,
        _environment: LeanEnvironment,
        _payload: dict[str, Any],
    ) -> dict[str, Any]:
        raise LeanDeclarationBackendError(
            "LEAN_DECLARATION_NOT_FOUND",
            "Lean did not find the exact declaration 'Missing.name'.",
        )


def test_search_adapter_exposes_bounded_computed_retrieval() -> None:
    backend = FakeBackend(
        {
            "operation": "search",
            "declarations": [
                {
                    "name": "irrational_sqrt_two",
                    "type": "Irrational √2",
                    "kind": "THEOREM",
                    "namespace": None,
                    "docstring": None,
                    "source": {
                        "module": "Mathlib.NumberTheory.Real.Irrational",
                        "line": 143,
                        "column": 8,
                        "end_line": 143,
                        "end_column": 27,
                    },
                    "match_reasons": ["NAME_SUBSTRING"],
                }
            ],
            "scanned_declarations": 20_001,
            "stop_reason": "RESULT_LIMIT",
        }
    )
    adapter = LeanDeclarationSearchAdapter(
        LeanDeclarationService(backend),
        _RUNTIME,
    )

    result = adapter.invoke(
        CapabilityRequest(
            capability_id="lean.declaration.search",
            mode=CapabilityMode.EXPLORE,
            input={
                "environment": "MATHLIB",
                "name_contains": "irrational_sqrt_two",
                "result_limit": 1,
            },
        )
    )

    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.completeness.status is CapabilityCompletenessStatus.PARTIAL
    assert result.output["environment_digest"] == _DIGEST
    assert result.output["declarations"][0]["name"] == "irrational_sqrt_two"
    assert result.scope is not None
    assert result.scope.parameters["matching"] == (
        "case-sensitive name substring and exact constants occurring in the "
        "elaborated type"
    )
    assert backend.calls[0][1] == {
        "operation": "search",
        "declaration_name": None,
        "name_contains": "irrational_sqrt_two",
        "type_constants": [],
        "namespace_prefixes": [],
        "target_module_prefixes": [],
        "kinds": [],
        "limit": 1,
    }


def test_exhausted_search_reports_computed_complete_coverage() -> None:
    backend = FakeBackend(
        {
            "operation": "search",
            "declarations": [],
            "scanned_declarations": 626_944,
            "stop_reason": "EXHAUSTED",
        }
    )
    adapter = LeanDeclarationSearchAdapter(
        LeanDeclarationService(backend),
        _RUNTIME,
    )

    result = adapter.invoke(
        CapabilityRequest(
            capability_id="lean.declaration.search",
            mode=CapabilityMode.EXPLORE,
            input={
                "environment": "MATHLIB",
                "type_pattern": {"constants": ["Jacobian.DoesNotExist"]},
            },
        )
    )

    assert result.completeness.status is CapabilityCompletenessStatus.COMPLETE
    assert result.completeness.assurance_level is CapabilityAssuranceLevel.COMPUTED
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED


def test_inspect_adapter_returns_docs_without_promoting_the_theorem() -> None:
    backend = FakeBackend(
        {
            "operation": "inspect",
            "declaration": {
                "name": "Nat.add",
                "type": "Nat → Nat → Nat",
                "kind": "DEFINITION",
                "namespace": "Nat",
                "docstring": "Addition of natural numbers.",
                "source": None,
                "match_reasons": [],
            },
        }
    )
    adapter = LeanDeclarationInspectAdapter(
        LeanDeclarationService(backend),
        _RUNTIME,
    )

    result = adapter.invoke(
        CapabilityRequest(
            capability_id="lean.declaration.inspect",
            mode=CapabilityMode.EXPLORE,
            input={
                "environment": "CORE",
                "declaration_name": "Nat.add",
            },
        )
    )

    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.assurance.verification_record_uri is None
    assert result.output["declaration"]["docstring"].startswith("Addition")
    assert result.output["environment_digest"] == _DIGEST


def test_missing_declaration_is_an_explicit_failed_operation() -> None:
    adapter = LeanDeclarationInspectAdapter(
        LeanDeclarationService(MissingDeclarationBackend()),
        _RUNTIME,
    )

    with pytest.raises(CapabilityInvocationError) as raised:
        adapter.invoke(
            CapabilityRequest(
                capability_id="lean.declaration.inspect",
                mode=CapabilityMode.EXPLORE,
                input={
                    "environment": "CORE",
                    "declaration_name": "Missing.name",
                },
            )
        )

    assert raised.value.diagnostic.code == "LEAN_DECLARATION_NOT_FOUND"


def test_environment_identity_fails_closed_if_the_lean_executable_changes(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "lean"
    executable.write_bytes(b"pinned lean executable")
    digest = "sha256:" + hashlib.sha256(executable.read_bytes()).hexdigest()
    runtime = _RUNTIME.model_copy(update={"digest": digest, "features": ("CORE",)})
    backend = LeanSubprocessDeclarationBackend(
        lean_executable=executable,
        mathlib_runtime=None,
        provider_runtime=runtime,
    )

    assert backend.environment_digest(LeanEnvironment.CORE).startswith("sha256:")

    executable.write_bytes(b"changed lean executable")

    with pytest.raises(LeanDeclarationBackendError) as raised:
        backend.environment_digest(LeanEnvironment.CORE)

    assert raised.value.code == "LEAN_ENVIRONMENT_CHANGED"
