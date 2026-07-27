from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.lean_exploration import (
    LeanProofStateRequest,
    LeanProofStateTransitionArtifact,
)


def test_proof_state_request_has_hard_structured_output_bounds() -> None:
    with pytest.raises(ValidationError):
        LeanProofStateRequest(statement="True", tactic="trivial", max_goals=65)
    with pytest.raises(ValidationError):
        LeanProofStateRequest(
            statement="True",
            tactic="trivial",
            max_local_declarations=257,
        )


def test_transition_binds_rendered_and_typed_goal_counts() -> None:
    with pytest.raises(ValidationError, match="typed goals"):
        LeanProofStateTransitionArtifact(
            environment="CORE",
            environment_digest="sha256:" + "a" * 64,
            source_digest="sha256:" + "b" * 64,
            statement="True",
            proof_prefix=(),
            tactic="skip",
            input_state_uri="artifact://sha256/" + "c" * 64,
            input_state_digest="sha256:" + "d" * 64,
            replay_source="skip",
            goals=("⊢ True",),
            typed_goals=(),
            goal_count=1,
            successor_states=(),
            accepted=True,
            completed=False,
            messages=(),
            diagnostics=(),
            lean_version="4.31.0",
            lean_commit="abc",
        )
