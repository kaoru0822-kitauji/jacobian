from __future__ import annotations

import json
from pathlib import Path

from benchmarks.tooling.external_reasoning_observer import observe_external_reasoning


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _server_log() -> str:
    first_argument_digest = "sha256:" + "1" * 64
    second_argument_digest = "sha256:" + "2" * 64
    return "\n".join(
        [
            "INFO MCP tool call tool=math.find status=success "
            "request_digest=aaaaaaaaaaaaaaaa trace_digest=none "
            "trace_source=none duration_ms=12.375 response_bytes=321 "
            f"argument_digest={first_argument_digest}",
            "INFO MCP capability attempt request_digest=bbbbbbbbbbbbbbbb "
            "trace_digest=none trace_source=none "
            "capability_id=matrix.determinant.compute capability_version=1.0.0 "
            "mode=EXPLORE execution_status=COMPLETED assurance=COMPUTED "
            "diagnostic_codes=none attempt_duration_ms=8.250 "
            "operation_runtime_ms=1.5 response_bytes=456 "
            f"argument_digest={second_argument_digest}",
            "INFO MCP tool call tool=math.run status=success "
            "request_digest=bbbbbbbbbbbbbbbb trace_digest=none "
            "trace_source=none duration_ms=9.500 response_bytes=456 "
            f"argument_digest={second_argument_digest}",
        ]
    )


def test_observer_preserves_server_facts_and_only_explicit_messages(
    tmp_path: Path,
) -> None:
    trace = _write(
        tmp_path / "codex.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "agent_message",
                            "text": (
                                "I will inspect /Users/alice/private and use "
                                "Bearer top-secret-token before computing."
                            ),
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "reasoning",
                            "text": "hidden reasoning must not be retained",
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "mcp_tool_call",
                            "arguments": {"secret": "never retain tool arguments"},
                            "result": {"secret": "never retain tool results"},
                        },
                    }
                ),
            ]
        ),
    )
    server_log = _write(tmp_path / "mcp.log", _server_log())

    report = observe_external_reasoning(
        trial_id="trial-01",
        agent_trace=trace,
        server_log=server_log,
    ).model_dump(mode="json")

    assert report["status"] == "COMPLETE"
    assert report["causal_claim_authorized"] is False
    assert report["affects_mathematical_assurance"] is False
    assert len(report["explicit_summaries"]) == 1
    summary = report["explicit_summaries"][0]
    assert summary["text"] == (
        "I will inspect [REDACTED_HOME]/private and use "
        "[REDACTED_BEARER] before computing."
    )
    assert summary["redaction_count"] == 2
    rendered = json.dumps(report)
    assert "hidden reasoning" not in rendered
    assert "never retain tool arguments" not in rendered
    assert "never retain tool results" not in rendered

    assert [event["kind"] for event in report["server_events"]] == [
        "TOOL_CALL",
        "CAPABILITY_ATTEMPT",
        "TOOL_CALL",
    ]
    assert report["server_events"][0] == {
        "kind": "TOOL_CALL",
        "sequence": 1,
        "trial_id": "trial-01",
        "tool": "math.find",
        "status": "success",
        "request_digest": "aaaaaaaaaaaaaaaa",
        "trace_digest": "none",
        "trace_source": "none",
        "duration_ms": "12.375",
        "response_bytes": 321,
        "argument_digest": "sha256:" + "1" * 64,
        "correlation": "SERVER_REQUEST_DIGEST",
    }
    attempt = report["server_events"][1]
    assert attempt["capability_id"] == "matrix.determinant.compute"
    assert attempt["execution_status"] == "COMPLETED"
    assert attempt["assurance"] == "COMPUTED"
    assert attempt["diagnostic_codes"] == []
    assert report["metrics"] == {
        "server_event_candidates": 3,
        "server_events_recorded": 3,
        "server_event_coverage": 1.0,
        "tool_calls_recorded": 2,
        "capability_attempts_recorded": 1,
        "explicit_summaries_recorded": 1,
    }


def test_atif_uses_agent_message_but_excludes_reasoning_content(tmp_path: Path) -> None:
    trace = _write(
        tmp_path / "trajectory.json",
        json.dumps(
            {
                "schema_version": "ATIF-v1.7",
                "agent": {"name": "codex", "version": "0.147.0"},
                "steps": [
                    {"step_id": 1, "source": "user", "message": "Solve it."},
                    {
                        "step_id": 2,
                        "source": "agent",
                        "message": "I found a relevant exact determinant capability.",
                        "reasoning_content": "private derivation",
                    },
                    {
                        "step_id": 3,
                        "source": "agent",
                        "message": "copied summary",
                        "is_copied_context": True,
                    },
                ],
            }
        ),
    )
    server_log = _write(tmp_path / "mcp.log", _server_log())

    report = observe_external_reasoning(
        trial_id="atif-trial",
        agent_trace=trace,
        server_log=server_log,
    ).model_dump(mode="json")

    assert report["status"] == "COMPLETE"
    assert [item["text"] for item in report["explicit_summaries"]] == [
        "I found a relevant exact determinant capability."
    ]
    assert "private derivation" not in json.dumps(report)
    assert "copied summary" not in json.dumps(report)


def test_no_explicit_messages_is_complete_and_does_not_gate_server_log(
    tmp_path: Path,
) -> None:
    trace = _write(
        tmp_path / "codex.jsonl",
        json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10}}),
    )
    server_log = _write(tmp_path / "mcp.log", _server_log())

    report = observe_external_reasoning(
        trial_id="no-summary",
        agent_trace=trace,
        server_log=server_log,
    )

    assert report.status == "COMPLETE"
    assert report.explicit_summaries == ()
    assert len(report.server_events) == 3


def test_malformed_inputs_fail_observation_closed_but_retain_valid_events(
    tmp_path: Path,
) -> None:
    trace = _write(
        tmp_path / "codex.jsonl",
        "\n".join(
            [
                "{not-json",
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "agent_message", "text": "Still visible."},
                    }
                ),
            ]
        ),
    )
    server_log = _write(
        tmp_path / "mcp.log",
        "INFO MCP tool call tool=math.find status=success request_digest=broken\n"
        + _server_log(),
    )

    report = observe_external_reasoning(
        trial_id="partial",
        agent_trace=trace,
        server_log=server_log,
    )

    assert report.status == "INCOMPLETE"
    assert len(report.server_events) == 3
    assert [item.text for item in report.explicit_summaries] == ["Still visible."]
    assert {diagnostic.code for diagnostic in report.diagnostics} == {
        "MALFORMED_AGENT_TRACE_ENTRY",
        "MALFORMED_SERVER_EVENT",
    }
    assert report.metrics.server_event_candidates == 4
    assert report.metrics.server_events_recorded == 3
    assert report.metrics.server_event_coverage == 0.75


def test_summary_is_bounded_by_utf8_bytes_after_redaction(tmp_path: Path) -> None:
    trace = _write(
        tmp_path / "codex.jsonl",
        json.dumps(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "é" * 400},
            }
        ),
    )
    server_log = _write(tmp_path / "mcp.log", _server_log())

    report = observe_external_reasoning(
        trial_id="bounded",
        agent_trace=trace,
        server_log=server_log,
    )

    summary = report.explicit_summaries[0]
    assert summary.truncated is True
    assert len(summary.text.encode("utf-8")) <= 512
    assert summary.original_utf8_bytes == 800


def test_rich_wrapped_runtime_log_is_normalized_without_losing_digest(
    tmp_path: Path,
) -> None:
    trace = _write(tmp_path / "codex.jsonl", "")
    digest = "815b1d6727e4a612ca3166cd88af142b05de72964f9575af923f471c402d0233"
    server_log = _write(
        tmp_path / "mcp.log",
        "\n".join(
            [
                "INFO MCP tool call tool=math.find          server.py:286",
                "     status=success",
                "     request_digest=d4735e3a265e16ee",
                "     trace_digest=d4735e3a",
                "     trace_source=request_id",
                "     duration_ms=162.258",
                "     response_bytes=12492",
                "     argument_digest=sha256:815b1d6727e4a6",
                "     12ca3166cd88af142b05de72964f9575af923",
                "     f471c402d0233",
            ]
        ),
    )

    report = observe_external_reasoning(
        trial_id="wrapped",
        agent_trace=trace,
        server_log=server_log,
    )

    assert report.status == "COMPLETE"
    event = report.server_events[0]
    assert event.trace_digest == "d4735e3a"
    assert event.argument_digest == "sha256:" + digest
