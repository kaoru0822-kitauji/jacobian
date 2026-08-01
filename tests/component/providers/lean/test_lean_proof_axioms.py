from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from jacobian.artifacts import ArtifactService
from jacobian.contracts.capabilities import (
    CapabilityInstallTier,
    CapabilityMode,
    CapabilityProviderAvailability,
    CapabilityProviderDigestKind,
    CapabilityProviderRuntime,
    CapabilityRequest,
)
from jacobian.contracts.lean import LeanEnvironment
from jacobian.lean_frontend import proof_axioms
from jacobian.lean_frontend.proof_axioms import install_lean_proof_axioms_capability
from jacobian.schema_registry import SchemaRegistry
from jacobian.store import ArtifactStore


def test_proof_hole_inspection_ignores_strings_and_identifiers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = CapabilityProviderRuntime(
        provider="jacobian.lean4",
        availability=CapabilityProviderAvailability.AVAILABLE,
        version="4.31.0",
        digest="sha256:" + "a" * 64,
        digest_kind=CapabilityProviderDigestKind.EXECUTABLE,
        platform="test",
        install_tier=CapabilityInstallTier.T3,
        license_id="Apache-2.0",
        features=("CORE",),
    )
    proof = (
        'by let label : String := "'
        + ("sorry " * 65)
        + "\"; let admit' : Nat := 0; exact True.intro"
    )
    monkeypatch.setattr(
        proof_axioms,
        "_manifest_digest",
        lambda _environment: None,
    )
    monkeypatch.setattr(
        "jacobian_checkers.lean4._run_lean",
        lambda _source, *, environment_name: SimpleNamespace(
            stdout="'jacobian_theorem' does not depend on any axioms\n",
            stderr="",
            returncode=0,
        ),
    )

    with ArtifactStore(tmp_path) as store:
        schemas = SchemaRegistry(store)
        artifacts = ArtifactService(store, schemas)
        adapter, _installation = install_lean_proof_axioms_capability(
            store,
            schemas,
            artifacts,
            {LeanEnvironment.CORE: SimpleNamespace(lean_commit="lean-test")},
            runtime,
        )
        result = adapter.invoke(
            CapabilityRequest(
                capability_id="lean.proof.axioms.inspect",
                mode=CapabilityMode.EXPLORE,
                input={
                    "environment": "CORE",
                    "statement": "True",
                    "proof": proof,
                },
            )
        )

    assert result.output["sorry_count"] == 0
    assert result.output["admit_count"] == 0


def test_proof_holes_are_counted_but_not_rejected_as_commands() -> None:
    proof_axioms._validate_source("True", "by sorry")
    assert proof_axioms._proof_hole_counts("by sorry admit") == (1, 1)


def test_proof_hole_count_is_bounded_before_artifact_validation() -> None:
    with pytest.raises(ValueError, match="more than 64"):
        proof_axioms._validate_source("True", "by " + " ".join(["sorry"] * 65))
