from __future__ import annotations

import json
from pathlib import Path

import pytest

from jacobian.contracts.capabilities import CapabilityMode
from jacobian.contracts.reasoning import ReasoningWriteRequest
from jacobian.reasoning_log import ReasoningLogService, ReasoningProtocolError
from jacobian.storage.repository import ArtifactRepository


def _write(service: ReasoningLogService, **values: object):
    return service.write(ReasoningWriteRequest.model_validate(values))


def test_reasoning_log_enforces_one_complete_serial_cycle(tmp_path: Path) -> None:
    with ArtifactRepository(tmp_path) as store:
        service = ReasoningLogService(store)
        plan = _write(service, phase="PLAN", summary="Compute one exact invariant.")
        before = _write(
            service,
            phase="BEFORE_TOOL",
            summary="Use the installed exact operation.",
            run_id=plan.run_id,
            capability_id="integer.compute.gcd",
            mode="EXPLORE",
        )
        assert before.call_id is not None
        with pytest.raises(ReasoningProtocolError, match="waiting"):
            _write(
                service,
                phase="BEFORE_TOOL",
                summary="Cannot overlap calls.",
                run_id=plan.run_id,
                capability_id="integer.compute.gcd",
                mode="EXPLORE",
            )
        service.claim_call(
            plan.run_id,
            before.call_id,
            "integer.compute.gcd",
            CapabilityMode.EXPLORE,
            "sha256:" + "1" * 64,
        )
        with pytest.raises(ReasoningProtocolError, match="pending BEFORE_TOOL"):
            service.claim_call(
                plan.run_id,
                before.call_id,
                "integer.compute.gcd",
                CapabilityMode.EXPLORE,
                "sha256:" + "1" * 64,
            )
        service.finish_call(
            plan.run_id,
            before.call_id,
            "integer.compute.gcd",
            CapabilityMode.EXPLORE,
            "sha256:" + "1" * 64,
            execution_status="ERROR",
            diagnostic_codes=("FIXTURE_ERROR",),
        )
        with pytest.raises(ReasoningProtocolError, match="requires every"):
            _write(service, phase="FINAL", summary="Too early.", run_id=plan.run_id)
        _write(
            service,
            phase="AFTER_TOOL",
            summary="The operational error is a non-conclusion.",
            run_id=plan.run_id,
            call_id=before.call_id,
        )
        final = _write(
            service,
            phase="FINAL",
            summary="No mathematical claim was established.",
            run_id=plan.run_id,
        )
        assert final.state.value == "FINALIZED"
        events = [
            json.loads(line) for line in service.inspect_jsonl(plan.run_id).splitlines()
        ]
        assert [event["kind"] for event in events] == [
            "PLAN",
            "BEFORE_TOOL",
            "CAPABILITY_STARTED",
            "CAPABILITY_FINISHED",
            "AFTER_TOOL",
            "FINAL",
        ]


def test_runtime_recovery_marks_started_call_interrupted(tmp_path: Path) -> None:
    with ArtifactRepository(tmp_path) as store:
        service = ReasoningLogService(store)
        plan = _write(service, phase="PLAN", summary="Plan.")
        before = _write(
            service,
            phase="BEFORE_TOOL",
            summary="Call.",
            run_id=plan.run_id,
            capability_id="integer.compute.gcd",
            mode="EXPLORE",
        )
        assert before.call_id is not None
        service.claim_call(
            plan.run_id,
            before.call_id,
            "integer.compute.gcd",
            CapabilityMode.EXPLORE,
            "sha256:" + "2" * 64,
        )
        recovered = ReasoningLogService(store)
        assert recovered.inspect(plan.run_id)[-1].kind == "CAPABILITY_STARTED"
        recovered.recover_interrupted_calls(stale_after_seconds=0)
        last = recovered.inspect(plan.run_id)[-1]
        assert last.kind == "CAPABILITY_FINISHED"
        assert last.payload["diagnostic_codes"] == ["PROCESS_INTERRUPTED"]
