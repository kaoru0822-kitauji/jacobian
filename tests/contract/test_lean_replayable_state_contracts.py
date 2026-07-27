from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.lean_exploration import (
    LeanProofStateArtifact,
    LeanProofStateRequest,
)

STATE_URI = "artifact://sha256/" + "a" * 64
DIGEST = "sha256:" + "b" * 64


@pytest.mark.contract
def test_state_request_accepts_uri_without_replacement_source() -> None:
    request = LeanProofStateRequest(state_uri=STATE_URI, tactic="constructor")

    assert request.statement is None
    assert request.proof_prefix == ()


@pytest.mark.contract
def test_state_request_rejects_uri_with_replacement_prefix() -> None:
    with pytest.raises(ValidationError, match="cannot be combined"):
        LeanProofStateRequest(
            state_uri=STATE_URI,
            proof_prefix=("intro P",),
            tactic="constructor",
        )


@pytest.mark.contract
def test_state_artifact_binds_completion_to_normalized_goals() -> None:
    with pytest.raises(ValidationError, match="completion"):
        LeanProofStateArtifact(
            environment="CORE",
            environment_digest=DIGEST,
            source_digest=DIGEST,
            statement="True",
            tactic_prefix=(),
            normalized_goals=("⊢ True",),
            state_digest=DIGEST,
            completed=True,
            imports=("Init",),
            lean_version="4.31.0",
            lean_commit="lean-commit",
        )
