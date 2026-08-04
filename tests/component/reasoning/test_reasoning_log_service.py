from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
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
            interpretation_status="RESULT_UNAVAILABLE",
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


def test_restarted_runtime_can_explicitly_close_an_interrupted_call(
    tmp_path: Path,
) -> None:
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
        _write(
            recovered,
            phase="AFTER_TOOL",
            summary="The previous runtime ended before returning a result.",
            run_id=plan.run_id,
            call_id=before.call_id,
            interpretation_status="RESULT_UNAVAILABLE",
        )
        events = recovered.inspect(plan.run_id)
        assert events[-2].kind == "CAPABILITY_FINISHED"
        assert events[-2].payload["diagnostic_codes"] == ["PROCESS_INTERRUPTED"]
        assert events[-1].kind == "AFTER_TOOL"


def test_current_runtime_cannot_abandon_its_running_call(tmp_path: Path) -> None:
    with ArtifactRepository(tmp_path) as store:
        service = ReasoningLogService(store, runtime_instance_id="runtime-a")
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
            "sha256:" + "3" * 64,
        )
        with pytest.raises(ReasoningProtocolError, match="still owned"):
            _write(
                service,
                phase="AFTER_TOOL",
                summary="Cannot abandon a live call.",
                run_id=plan.run_id,
                call_id=before.call_id,
                interpretation_status="RESULT_UNAVAILABLE",
            )


def test_completion_must_match_the_started_call(tmp_path: Path) -> None:
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
        request_digest = "sha256:" + "4" * 64
        service.claim_call(
            plan.run_id,
            before.call_id,
            "integer.compute.gcd",
            CapabilityMode.EXPLORE,
            request_digest,
        )
        with pytest.raises(ReasoningProtocolError, match="differs from the started"):
            service.finish_call(
                plan.run_id,
                before.call_id,
                "integer.compute.gcd",
                CapabilityMode.EXPLORE,
                "sha256:" + "5" * 64,
                execution_status="ERROR",
            )
        assert service.inspect(plan.run_id)[-1].kind == "CAPABILITY_STARTED"


def test_concurrent_claims_start_exactly_one_call(tmp_path: Path) -> None:
    with ArtifactRepository(tmp_path) as store:
        service = ReasoningLogService(store)
        plan = _write(service, phase="PLAN", summary="Plan.")
        before = _write(
            service,
            phase="BEFORE_TOOL",
            summary="Call once.",
            run_id=plan.run_id,
            capability_id="integer.compute.gcd",
            mode="EXPLORE",
        )
        assert before.call_id is not None

        def claim() -> str:
            try:
                service.claim_call(
                    plan.run_id,
                    before.call_id or "",
                    "integer.compute.gcd",
                    CapabilityMode.EXPLORE,
                    "sha256:" + "6" * 64,
                )
            except ReasoningProtocolError:
                return "rejected"
            return "claimed"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _index: claim(), range(2)))

        assert sorted(outcomes) == ["claimed", "rejected"]
        assert [event.kind for event in service.inspect(plan.run_id)].count(
            "CAPABILITY_STARTED"
        ) == 1
