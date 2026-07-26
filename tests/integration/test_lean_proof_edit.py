from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from jacobian.capabilities import CapabilityInvocationError
from jacobian.contracts.capabilities import (
    CapabilityAssuranceLevel,
    CapabilityMode,
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


def test_exact_proof_edit_is_bound_to_authorized_lean_check(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="lean.proof_edit.validate",
            mode=CapabilityMode.VERIFY,
            input={
                "environment": "CORE",
                "statement": "True",
                "original_proof": "by\n  exact True.intro",
                "edited_proof": "by\n  trivial",
            },
        )
    )

    assert result.output["accepted"] is True
    assert result.assurance.level is CapabilityAssuranceLevel.VERIFIED
    assert result.assurance.verification_record_uri == (
        result.output["verification_record_uri"]
    )
    assert result.output["proof_edit_uri"] in result.artifact_uris
    edit = kernel.store.get(result.output["proof_edit_uri"])
    assert edit.payload["edited_proof"] == "by\n  trivial"
    assert set(edit.manifest.parents) == {
        result.output["claim_uri"],
        result.output["candidate_uri"],
        result.output["certificate_uri"],
    }


def test_proof_edit_rejects_holes_before_checker_invocation(tmp_path: Path) -> None:
    kernel = JacobianKernel(tmp_path, install_references=True)

    with pytest.raises(CapabilityInvocationError) as raised:
        kernel.capabilities.invoke(
            CapabilityRequest(
                capability_id="lean.proof_edit.validate",
                mode=CapabilityMode.VERIFY,
                input={
                    "environment": "CORE",
                    "statement": "True",
                    "original_proof": "by\n  trivial",
                    "edited_proof": "by\n  sorry",
                },
            )
        )

    assert raised.value.diagnostic.code == "INVALID_LEAN_PROOF_EDIT_REQUEST"
