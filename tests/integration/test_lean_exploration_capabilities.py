from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityRequest,
)
from jacobian.kernel import JacobianKernel

pytestmark = [
    pytest.mark.integration,
    pytest.mark.external_backend,
    pytest.mark.lean_runtime,
    pytest.mark.skipif(shutil.which("lean") is None, reason="Lean is not installed"),
    pytest.mark.usefixtures("initialized_kernel_store"),
]


def test_apply_tactic_exposes_child_goals_and_replay_source(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="lean.proof_state.apply_tactic",
            input={
                "environment": "CORE",
                "statement": "(P Q : Prop) → P → Q → P ∧ Q",
                "proof_prefix": ["intro P Q hP hQ"],
                "tactic": "constructor",
            },
        )
    )

    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.output["completed"] is False
    assert result.output["goal_count"] == 2
    assert all("⊢" in goal for goal in result.output["goals"])
    assert result.output["accepted"] is True
    assert len(result.output["successor_states"]) == 1
    assert result.output["input_state_uri"] in result.artifact_uris
    assert result.output["successor_states"][0]["state_uri"] in result.artifact_uris
    assert result.output["transition_uri"] in result.artifact_uris
    assert result.output["replay_source"].endswith("intro P Q hP hQ\n  constructor")


def test_apply_tactic_returns_structured_failure_without_conclusion(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="lean.proof_state.apply_tactic",
            input={
                "environment": "CORE",
                "statement": "(P Q : Prop) → P → Q",
                "proof_prefix": ["intro P Q hP"],
                "tactic": "exact hP",
            },
        )
    )

    assert result.execution.status.value == "COMPLETED"
    assert result.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert result.output["accepted"] is False
    assert result.output["successor_states"] == []
    assert any(
        diagnostic["severity"] == "ERROR"
        for diagnostic in result.output["diagnostics"]
    )


def test_retrieve_premises_returns_exact_mathlib_suggestion(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    suggested = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="lean.retrieve.premises",
            input={
                "environment": "MATHLIB",
                "statement": "(n : Nat) → Nat.gcd n 0 = n",
                "proof_prefix": ["intro n"],
                "limit": 5,
            },
        )
    )

    empty = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="lean.retrieve.premises",
            input={
                "environment": "MATHLIB",
                "statement": "(P Q : Prop) → P → Q",
                "proof_prefix": ["intro P Q hP"],
                "limit": 5,
            },
        )
    )

    assert suggested.assurance.level is CapabilityAssuranceLevel.COMPUTED
    assert suggested.output["candidates"]
    assert suggested.output["candidates"][0]["tactic"] == ("exact Nat.gcd_zero_right n")
    assert (
        "Nat.gcd_zero_right" in suggested.output["candidates"][0]["declaration_names"]
    )
    assert suggested.output["retrieval_uri"] in suggested.artifact_uris
    assert empty.execution.status.value == "COMPLETED"
    assert empty.output["candidates"] == []
    assert empty.output["exhaustive"] is False


def test_kernel_can_ablate_lean_capabilities_without_removing_checker(
    tmp_path: Path,
) -> None:
    kernel = JacobianKernel(
        tmp_path,
        install_references=True,
        capability_exclusions=frozenset(
            {
                "lean.proof_state.apply_tactic",
                "lean.retrieve.premises",
            }
        ),
    )
    capability_ids = {
        descriptor.capability_id
        for descriptor in kernel.capabilities.catalog().capabilities
    }

    assert "lean.check" in capability_ids
    assert "lean.proof_state.apply_tactic" not in capability_ids
    assert "lean.retrieve.premises" not in capability_ids
