from __future__ import annotations

import pytest
from pydantic import ValidationError

from jacobian.contracts.reasoning import ReasoningWriteRequest


def test_reasoning_phase_contracts_are_closed_and_bounded() -> None:
    plan = ReasoningWriteRequest(phase="PLAN", summary="Inspect the exact claim.")
    assert plan.run_id is None

    with pytest.raises(ValidationError, match="phase contract"):
        ReasoningWriteRequest(
            phase="PLAN",
            summary="invalid",
            run_id="00000000-0000-4000-8000-000000000000",
        )
    with pytest.raises(ValidationError, match="512 characters"):
        ReasoningWriteRequest(phase="PLAN", summary="界" * 513)
    with pytest.raises(ValidationError):
        ReasoningWriteRequest(phase="PLAN", summary="ok", hidden_reasoning="secret")


def test_before_and_after_require_exact_binding_fields() -> None:
    run_id = "00000000-0000-4000-8000-000000000000"
    call_id = "11111111-1111-4111-8111-111111111111"
    before = ReasoningWriteRequest(
        phase="BEFORE_TOOL",
        summary="Compute an exact finite value.",
        run_id=run_id,
        capability_id="integer.compute.gcd",
        mode="EXPLORE",
    )
    after = ReasoningWriteRequest(
        phase="AFTER_TOOL",
        summary="The completed result is computed, not independently verified.",
        run_id=run_id,
        call_id=call_id,
        interpretation_status="INTERPRETED",
        reported_execution_status="COMPLETED",
        reported_assurance_level="COMPUTED",
        reported_completeness_status="NOT_APPLICABLE",
    )
    assert before.capability_id == "integer.compute.gcd"
    assert after.call_id == call_id


def test_after_tool_distinguishes_interpreted_and_unavailable_results() -> None:
    binding = {
        "phase": "AFTER_TOOL",
        "summary": "No result content was available after restart.",
        "run_id": "00000000-0000-4000-8000-000000000000",
        "call_id": "11111111-1111-4111-8111-111111111111",
    }
    unavailable = ReasoningWriteRequest(
        **binding,
        interpretation_status="RESULT_UNAVAILABLE",
    )
    assert unavailable.reported_execution_status is None

    with pytest.raises(ValidationError, match="all reported result fields"):
        ReasoningWriteRequest(
            **binding,
            interpretation_status="INTERPRETED",
            reported_execution_status="COMPLETED",
        )
    with pytest.raises(ValidationError, match="require INTERPRETED"):
        ReasoningWriteRequest(
            **binding,
            interpretation_status="RESULT_UNAVAILABLE",
            reported_execution_status="ERROR",
        )
