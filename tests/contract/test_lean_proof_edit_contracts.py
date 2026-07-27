from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.lean_proof_edit import (
    LeanProofEditArtifact,
    LeanProofEditRequest,
)

_URI = "artifact://sha256/" + "a" * 64
_OTHER_URI = "artifact://sha256/" + "b" * 64


def test_proof_edit_request_requires_an_actual_edit() -> None:
    with pytest.raises(ValidationError, match="must differ"):
        LeanProofEditRequest(
            statement="True",
            original_proof="by trivial",
            edited_proof="by trivial",
        )


def test_proof_edit_acceptance_requires_verification_record() -> None:
    with pytest.raises(ValidationError, match="verification record"):
        LeanProofEditArtifact(
            environment="CORE",
            statement="True",
            original_proof="by exact True.intro",
            edited_proof="by trivial",
            unified_diff="--- original\n+++ edited\n",
            baseline_checker_execution_status="COMPLETED",
            baseline_accepted=True,
            baseline_candidate_uri=_URI,
            baseline_certificate_uri=_URI,
            baseline_verification_record_uri=_URI,
            checker_execution_status="COMPLETED",
            accepted=True,
            claim_uri=_URI,
            candidate_uri=_URI,
            certificate_uri=_URI,
        )


def test_rejected_proof_edit_retains_checker_record_as_evidence() -> None:
    artifact = LeanProofEditArtifact(
        environment="CORE",
        statement="True",
        original_proof="by exact True.intro",
        edited_proof="by trivial",
        unified_diff="--- original\n+++ edited\n",
        baseline_checker_execution_status="COMPLETED",
        baseline_accepted=True,
        baseline_candidate_uri=_URI,
        baseline_certificate_uri=_URI,
        baseline_verification_record_uri=_URI,
        checker_execution_status="COMPLETED",
        accepted=False,
        claim_uri=_URI,
        candidate_uri=_URI,
        certificate_uri=_URI,
        verification_record_uri=_OTHER_URI,
    )

    assert artifact.verification_record_uri == _OTHER_URI


def test_accepted_proof_edit_requires_verified_baseline() -> None:
    with pytest.raises(ValidationError, match="accepted baseline"):
        LeanProofEditArtifact(
            environment="CORE",
            statement="True",
            original_proof="by exact False.elim (by trivial)",
            edited_proof="by trivial",
            unified_diff="--- original\n+++ edited\n",
            baseline_checker_execution_status="COMPLETED",
            baseline_accepted=False,
            baseline_candidate_uri=_URI,
            baseline_certificate_uri=_URI,
            checker_execution_status="COMPLETED",
            accepted=True,
            claim_uri=_URI,
            candidate_uri=_URI,
            certificate_uri=_URI,
            verification_record_uri=_URI,
        )
