from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.lean_proof_edit import (
    LeanProofEditArtifact,
    LeanProofEditRequest,
)

_URI = "artifact://sha256/" + "a" * 64


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
            checker_execution_status="COMPLETED",
            accepted=True,
            claim_uri=_URI,
            candidate_uri=_URI,
            certificate_uri=_URI,
        )


def test_rejected_proof_edit_cannot_claim_verification_record() -> None:
    with pytest.raises(ValidationError, match="verification record"):
        LeanProofEditArtifact(
            environment="CORE",
            statement="True",
            original_proof="by exact True.intro",
            edited_proof="by trivial",
            unified_diff="--- original\n+++ edited\n",
            checker_execution_status="COMPLETED",
            accepted=False,
            claim_uri=_URI,
            candidate_uri=_URI,
            certificate_uri=_URI,
            verification_record_uri=_URI,
        )
