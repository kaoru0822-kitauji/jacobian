"""Append-only operational reasoning-log service."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from jacobian.canonical import canonicalize_json
from jacobian.contracts.capabilities import CapabilityMode, CapabilityResult
from jacobian.contracts.reasoning import (
    ReasoningEvent,
    ReasoningNextRequired,
    ReasoningPhase,
    ReasoningRunState,
    ReasoningWriteRequest,
    ReasoningWriteResult,
)
from jacobian.storage.repository import ArtifactRepository

MAX_CALLS_PER_RUN = 64
INTERRUPTED_CALL_GRACE_SECONDS = 600


class ReasoningProtocolError(RuntimeError):
    """A recoverable violation of the external reasoning protocol."""

    def __init__(self, code: str, message: str, hint: str) -> None:
        super().__init__(message)
        self.code = code
        self.hint = hint


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonicalize_json(value)).hexdigest()


class ReasoningLogService:
    """Persist ordered model summaries and system-owned capability bindings."""

    def __init__(self, store: ArtifactRepository) -> None:
        self.store = store
        self.recover_interrupted_calls()

    def write(self, request: ReasoningWriteRequest) -> ReasoningWriteResult:
        if request.phase is ReasoningPhase.PLAN:
            return self._create_run(request.summary)
        assert request.run_id is not None
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            events = self._read_events(connection, request.run_id)
            state, pending = self._state(events)
            call_id: str | None
            if request.phase is ReasoningPhase.BEFORE_TOOL:
                if state is ReasoningRunState.FINALIZED:
                    self._raise(
                        "REASONING_RUN_FINALIZED",
                        "The reasoning run is finalized.",
                        "Start a new PLAN for further work.",
                    )
                if state is not ReasoningRunState.READY:
                    self._raise(
                        "REASONING_RUN_BUSY",
                        "This run is waiting for its current capability cycle.",
                        "Complete the indicated invoke or AFTER_TOOL before reserving another call.",
                    )
                if (
                    sum(event.kind == "BEFORE_TOOL" for event in events)
                    >= MAX_CALLS_PER_RUN
                ):
                    self._raise(
                        "REASONING_RUN_LIMIT",
                        "This run reached its 64-call limit.",
                        "Write FINAL and start a new PLAN if more work is required.",
                    )
                call_id = str(uuid4())
                event = self._append_event(
                    connection,
                    request.run_id,
                    "BEFORE_TOOL",
                    {
                        "summary": request.summary,
                        "call_id": call_id,
                        "capability_id": request.capability_id,
                        "mode": request.mode.value if request.mode else None,
                    },
                )
            elif request.phase is ReasoningPhase.AFTER_TOOL:
                if (
                    state is not ReasoningRunState.AWAITING_AFTER_TOOL
                    or pending != request.call_id
                ):
                    self._raise(
                        "REASONING_STATE_MISMATCH",
                        "AFTER_TOOL does not match the completed pending call.",
                        "Read the reasoning log and use the pending call_id after its capability result.",
                    )
                call_id = request.call_id
                event = self._append_event(
                    connection,
                    request.run_id,
                    "AFTER_TOOL",
                    {"summary": request.summary, "call_id": call_id},
                )
            else:
                if state is not ReasoningRunState.READY:
                    self._raise(
                        "REASONING_FINAL_BLOCKED",
                        "FINAL requires every capability call to have AFTER_TOOL.",
                        "Complete the current capability cycle before the final audit.",
                    )
                call_id = None
                event = self._append_event(
                    connection, request.run_id, "FINAL", {"summary": request.summary}
                )
            new_events = (*events, event)
            new_state, _ = self._state(new_events)
            return self._result(event, new_state, call_id)

    def _create_run(self, summary: str) -> ReasoningWriteResult:
        run_id = str(uuid4())
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO reasoning_runs(run_id) VALUES (?)", (run_id,)
            )
            event = self._append_event(connection, run_id, "PLAN", {"summary": summary})
            return self._result(event, ReasoningRunState.READY, None)

    def claim_call(
        self,
        run_id: str,
        call_id: str,
        capability_id: str,
        mode: CapabilityMode,
        request_digest: str,
    ) -> None:
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            events = self._read_events(connection, run_id)
            state, pending = self._state(events)
            if state is not ReasoningRunState.READY_TO_INVOKE or pending != call_id:
                self._raise(
                    "REASONING_CALL_MISMATCH",
                    "The invocation is not bound to the pending BEFORE_TOOL entry.",
                    "Use the run_id and call_id returned by the current BEFORE_TOOL entry.",
                )
            before = next(
                event for event in reversed(events) if event.kind == "BEFORE_TOOL"
            )
            if (
                before.payload.get("capability_id") != capability_id
                or before.payload.get("mode") != mode.value
            ):
                self._raise(
                    "REASONING_CALL_MISMATCH",
                    "The actual capability ID or mode differs from BEFORE_TOOL.",
                    "Invoke exactly the capability ID and mode reserved by BEFORE_TOOL.",
                )
            self._append_event(
                connection,
                run_id,
                "CAPABILITY_STARTED",
                {
                    "call_id": call_id,
                    "capability_id": capability_id,
                    "mode": mode.value,
                    "request_digest": request_digest,
                },
            )

    def finish_call(
        self,
        run_id: str,
        call_id: str,
        capability_id: str,
        mode: CapabilityMode,
        request_digest: str,
        *,
        result: CapabilityResult | None = None,
        execution_status: str | None = None,
        diagnostic_codes: tuple[str, ...] = (),
    ) -> None:
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            events = self._read_events(connection, run_id)
            state, pending = self._state(events)
            if state is not ReasoningRunState.TOOL_RUNNING or pending != call_id:
                self._raise(
                    "REASONING_CALL_MISMATCH",
                    "The capability completion has no matching started call.",
                    "Inspect the durable reasoning log before retrying.",
                )
            if result is None:
                payload: dict[str, Any] = {
                    "call_id": call_id,
                    "capability_id": capability_id,
                    "mode": mode.value,
                    "request_digest": request_digest,
                    "result_digest": None,
                    "execution_status": execution_status or "ERROR",
                    "assurance": None,
                    "completeness": None,
                    "scope_digest": None,
                    "artifact_uris": [],
                    "episode_uri": None,
                    "diagnostic_codes": list(diagnostic_codes),
                }
            else:
                serialized = result.model_dump(mode="json")
                payload = {
                    "call_id": call_id,
                    "capability_id": result.capability_id,
                    "capability_version": result.capability_version,
                    "mode": result.mode.value,
                    "request_digest": request_digest,
                    "result_digest": _digest(serialized),
                    "execution_status": result.execution.status.value,
                    "assurance": result.assurance.model_dump(mode="json"),
                    "completeness": result.completeness.model_dump(mode="json"),
                    "scope_digest": _digest(result.scope.model_dump(mode="json"))
                    if result.scope is not None
                    else None,
                    "artifact_uris": list(result.artifact_uris),
                    "episode_uri": result.episode_uri,
                    "diagnostic_codes": [item.code for item in result.diagnostics],
                }
            self._append_event(connection, run_id, "CAPABILITY_FINISHED", payload)

    def recover_interrupted_calls(
        self,
        *,
        stale_after_seconds: int = INTERRUPTED_CALL_GRACE_SECONDS,
    ) -> None:
        with self.store.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT run_id FROM reasoning_runs ORDER BY run_id"
            ).fetchall()
            for row in rows:
                events = self._read_events(connection, str(row["run_id"]))
                state, pending = self._state(events)
                if state is ReasoningRunState.TOOL_RUNNING and pending is not None:
                    started = next(
                        event
                        for event in reversed(events)
                        if event.kind == "CAPABILITY_STARTED"
                    )
                    started_at = datetime.fromisoformat(started.occurred_at)
                    age_seconds = (datetime.now(UTC) - started_at).total_seconds()
                    if age_seconds < stale_after_seconds:
                        continue
                    self._append_event(
                        connection,
                        str(row["run_id"]),
                        "CAPABILITY_FINISHED",
                        {
                            "call_id": pending,
                            "capability_id": started.payload["capability_id"],
                            "mode": started.payload["mode"],
                            "request_digest": started.payload["request_digest"],
                            "result_digest": None,
                            "execution_status": "ERROR",
                            "assurance": None,
                            "completeness": None,
                            "scope_digest": None,
                            "artifact_uris": [],
                            "episode_uri": None,
                            "diagnostic_codes": ["PROCESS_INTERRUPTED"],
                        },
                    )

    def inspect(self, run_id: str) -> tuple[ReasoningEvent, ...]:
        with self.store.connection() as connection:
            return self._read_events(connection, run_id)

    def inspect_jsonl(self, run_id: str) -> str:
        return (
            "\n".join(event.model_dump_json() for event in self.inspect(run_id)) + "\n"
        )

    def _read_events(
        self, connection: sqlite3.Connection, run_id: str
    ) -> tuple[ReasoningEvent, ...]:
        exists = connection.execute(
            "SELECT 1 FROM reasoning_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if exists is None:
            self._raise(
                "REASONING_RUN_NOT_FOUND",
                "The reasoning run does not exist in this tenant.",
                "Use the run_id returned by PLAN in the same tenant.",
            )
        rows = connection.execute(
            "SELECT event_json FROM reasoning_events WHERE run_id = ? ORDER BY sequence",
            (run_id,),
        ).fetchall()
        events = tuple(
            ReasoningEvent.model_validate(json.loads(bytes(row["event_json"])))
            for row in rows
        )
        previous: str | None = None
        for sequence, event in enumerate(events):
            unsigned = event.model_dump(mode="json", exclude={"event_digest"})
            if (
                event.sequence != sequence
                or event.previous_digest != previous
                or _digest(unsigned) != event.event_digest
            ):
                self._raise(
                    "REASONING_LOG_CORRUPT",
                    "The reasoning event chain failed integrity validation.",
                    "Stop using this run and inspect the tenant state offline.",
                )
            previous = event.event_digest
        return events

    def _append_event(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        kind: str,
        payload: dict[str, Any],
    ) -> ReasoningEvent:
        row = connection.execute(
            "SELECT sequence, event_digest FROM reasoning_events WHERE run_id = ? ORDER BY sequence DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        sequence = 0 if row is None else int(row["sequence"]) + 1
        previous = None if row is None else str(row["event_digest"])
        unsigned = {
            "schema_version": "1",
            "run_id": run_id,
            "sequence": sequence,
            "kind": kind,
            "occurred_at": datetime.now(UTC).isoformat(),
            "previous_digest": previous,
            "payload": payload,
        }
        event = ReasoningEvent.model_validate(
            {**unsigned, "event_digest": _digest(unsigned)}
        )
        connection.execute(
            "INSERT INTO reasoning_events(run_id, sequence, kind, call_id, event_json, event_digest) VALUES (?, ?, ?, ?, ?, ?)",
            (
                run_id,
                sequence,
                kind,
                payload.get("call_id"),
                canonicalize_json(event.model_dump(mode="json")),
                event.event_digest,
            ),
        )
        return event

    @staticmethod
    def _state(
        events: tuple[ReasoningEvent, ...],
    ) -> tuple[ReasoningRunState, str | None]:
        if not events or events[0].kind != "PLAN":
            raise ReasoningProtocolError(
                "REASONING_LOG_CORRUPT",
                "The run is missing its initial PLAN.",
                "Stop using this run and inspect the tenant state offline.",
            )
        last = events[-1]
        if last.kind in {"PLAN", "AFTER_TOOL"}:
            return ReasoningRunState.READY, None
        if last.kind == "BEFORE_TOOL":
            return ReasoningRunState.READY_TO_INVOKE, str(last.payload["call_id"])
        if last.kind == "CAPABILITY_STARTED":
            return ReasoningRunState.TOOL_RUNNING, str(last.payload["call_id"])
        if last.kind == "CAPABILITY_FINISHED":
            return ReasoningRunState.AWAITING_AFTER_TOOL, str(last.payload["call_id"])
        if last.kind == "FINAL":
            return ReasoningRunState.FINALIZED, None
        raise ReasoningProtocolError(
            "REASONING_LOG_CORRUPT",
            "The run ends in an unknown event state.",
            "Stop using this run and inspect the tenant state offline.",
        )

    @staticmethod
    def _result(
        event: ReasoningEvent, state: ReasoningRunState, call_id: str | None
    ) -> ReasoningWriteResult:
        next_required = {
            ReasoningRunState.READY: ReasoningNextRequired.BEFORE_TOOL_OR_FINAL,
            ReasoningRunState.READY_TO_INVOKE: ReasoningNextRequired.CAPABILITY_INVOKE,
            ReasoningRunState.TOOL_RUNNING: ReasoningNextRequired.CAPABILITY_INVOKE,
            ReasoningRunState.AWAITING_AFTER_TOOL: ReasoningNextRequired.AFTER_TOOL,
            ReasoningRunState.FINALIZED: ReasoningNextRequired.NONE,
        }[state]
        return ReasoningWriteResult(
            run_id=event.run_id,
            call_id=call_id,
            event_digest=event.event_digest,
            sequence=event.sequence,
            state=state,
            next_required=next_required,
            log_uri=f"reasoning://run/{event.run_id}",
        )

    @staticmethod
    def _raise(code: str, message: str, hint: str) -> None:
        raise ReasoningProtocolError(code, message, hint)


__all__ = [
    "INTERRUPTED_CALL_GRACE_SECONDS",
    "MAX_CALLS_PER_RUN",
    "ReasoningLogService",
    "ReasoningProtocolError",
]
