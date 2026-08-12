from __future__ import annotations

import json

import pytest
from benchmarks.tooling import trajectory_information as study


def _event(item: dict[str, object]) -> str:
    return json.dumps({"type": "item.completed", "item": item})


def test_visible_messages_exclude_reasoning_final_and_tool_payloads() -> None:
    payload = (
        "\n".join(
            [
                _event({"type": "agent_message", "text": "I found a route."}),
                _event({"type": "reasoning", "text": "private chain"}),
                _event(
                    {
                        "type": "mcp_tool_call",
                        "tool": "math.find",
                        "arguments": {"secret": "argument"},
                        "result": {"secret": "result"},
                    }
                ),
                _event({"type": "agent_message", "text": "Final answer."}),
            ]
        )
        + "\n"
    ).encode()

    messages, prefix_counts = study._visible_messages(payload)

    assert [message["text"] for message in messages] == ["I found a route."]
    assert prefix_counts == [1]
    rendered = json.dumps(messages)
    assert "private chain" not in rendered
    assert "argument" not in rendered
    assert "result" not in rendered
    assert "Final answer" not in rendered


def test_visible_messages_redact_and_bound_utf8() -> None:
    payload = (
        _event(
            {
                "type": "agent_message",
                "text": "Bearer secret " + "/home/alice/private " + "é" * 400,
            }
        )
        + "\n"
        + _event({"type": "agent_message", "text": "Final."})
        + "\n"
    ).encode()

    messages, _ = study._visible_messages(payload)

    assert len(messages) == 1
    assert len(str(messages[0]["text"]).encode()) <= 512
    assert messages[0]["truncated"] is True
    assert messages[0]["redaction_count"] == 2
    assert "secret" not in str(messages[0]["text"])
    assert "/home/alice" not in str(messages[0]["text"])


def test_server_projection_preserves_safe_typed_order() -> None:
    first = "sha256:" + "1" * 64
    second = "sha256:" + "2" * 64
    payload = "\n".join(
        [
            "INFO MCP tool call tool=math.find status=success "
            "request_digest=aaaaaaaaaaaaaaaa trace_digest=aaaaaaaa "
            "trace_source=request_id duration_ms=12.5 response_bytes=321 "
            f"argument_digest={first}",
            "INFO MCP capability attempt request_digest=bbbbbbbbbbbbbbbb "
            "trace_digest=bbbbbbbb trace_source=request_id "
            "capability_id=matrix.determinant.verify capability_version=1 "
            "execution_status=COMPLETED assurance=VERIFIED diagnostic_codes=none "
            "attempt_duration_ms=8.25 operation_runtime_ms=2 response_bytes=456 "
            f"argument_digest={second}",
            "INFO MCP tool call tool=math.run status=success "
            "request_digest=bbbbbbbbbbbbbbbb trace_digest=bbbbbbbb "
            "trace_source=request_id duration_ms=9.5 response_bytes=456 "
            f"argument_digest={second}",
        ]
    )

    events, coverage = study._server_events(payload)

    assert coverage == {"candidates": 3, "recorded": 3}
    assert [event["kind"] for event in events] == [
        "TOOL_CALL",
        "CAPABILITY_ATTEMPT",
        "TOOL_CALL",
    ]
    assert study._tool_action(events[-1], {"bbbbbbbbbbbbbbbb": events[1]}) == (
        "RUN_CHECKER"
    )
    assert study._checker_label(events) == "SUCCESS_WITHOUT_REJECTION"
    rendered = json.dumps(events)
    assert "payload" not in rendered
    assert "result" not in rendered


def test_malformed_server_candidate_fails_coverage_closed() -> None:
    events, coverage = study._server_events(
        "INFO MCP tool call tool=math.find status=success request_digest=broken"
    )

    assert events == []
    assert coverage == {"candidates": 1, "recorded": 0}


def test_condition_features_do_not_add_unselected_sources() -> None:
    row = study.Row(
        task_id="task-a",
        label="PASS",
        x_y={"xy": 1.0},
        b={"b": 2.0},
        tau={"tau": 3.0},
    )

    assert study._condition_features(row, "x+y") == {"xy": 1.0}
    assert study._condition_features(row, "x+y+b") == {"xy": 1.0, "b": 2.0}
    assert study._condition_features(row, "x+y+tau_tools") == {
        "xy": 1.0,
        "tau": 3.0,
    }
    assert study._condition_features(row, "x+y+b+tau_tools") == {
        "xy": 1.0,
        "b": 2.0,
        "tau": 3.0,
    }


def test_predictions_hold_out_complete_task_identity() -> None:
    rows = [
        study.Row("task-a", "A", {"x": 0.0}, {}, {}),
        study.Row("task-a", "B", {"x": 0.1}, {}, {}),
        study.Row("task-b", "A", {"x": 1.0}, {}, {}),
        study.Row("task-c", "B", {"x": 2.0}, {}, {}),
    ]

    predictions = study._predictions(rows, "x+y")

    assert len(predictions) == len(rows)
    assert {item["task_id"] for item in predictions} == {
        "task-a",
        "task-b",
        "task-c",
    }


def test_descriptive_fallback_reports_exact_transductive_contingencies() -> None:
    rows = [
        study.Row("task-a", "PASS", {"x": 0.0}, {}, {}),
        study.Row("task-b", "FAIL", {"x": 0.0}, {}, {}),
        study.Row("task-c", "PASS", {"x": 5.0}, {}, {}),
    ]

    predictions, contingencies = study._descriptive_predictions(rows, "x+y")

    assert len(predictions) == 3
    by_size = {item["row_count"]: item for item in contingencies}
    assert by_size[1]["task_count"] == 1
    assert by_size[1]["label_counts"] == {"PASS": 1}
    assert by_size[2]["task_count"] == 2
    assert by_size[2]["label_counts"] == {"FAIL": 1, "PASS": 1}
    assert all(
        str(item["signature_digest"]).startswith("sha256:") for item in contingencies
    )


@pytest.mark.parametrize(
    ("truth", "prediction", "expected"),
    [
        (("A", "B"), ("A", "B"), 1.0),
        (("A", "B"), ("B", "A"), 0.0),
    ],
)
def test_macro_f1(
    truth: tuple[str, ...], prediction: tuple[str, ...], expected: float
) -> None:
    metrics = study._metrics(
        [
            {"task_id": str(index), "truth": actual, "prediction": predicted}
            for index, (actual, predicted) in enumerate(
                zip(truth, prediction, strict=True)
            )
        ]
    )

    assert metrics["macro_f1"] == pytest.approx(expected)
