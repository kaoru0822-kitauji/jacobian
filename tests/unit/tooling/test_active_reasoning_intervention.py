from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from benchmarks.tooling import active_reasoning_intervention as study

ROOT = Path(__file__).parents[3]


def _item(item: dict[str, object]) -> str:
    return json.dumps({"type": "item.completed", "item": item})


def test_frozen_contract_is_paired_research_only_and_current() -> None:
    config = json.loads(
        (
            ROOT / "benchmarks/config/internalcot-trajectory-intervention-v1.json"
        ).read_text()
    )
    pairs = config["pair_plan"]
    tasks = config["dataset"]["tasks"]

    assert config["status"] == "FROZEN_BEFORE_MODEL_RUNS"
    assert config["production_change_authorized"] is False
    assert (
        config["frozen_against"]["git_sha"]
        == "f37a5b205ccdb3537db47e7e055e06ee514d6e62"
    )
    assert len(pairs) == 16
    assert len(tasks) == 8
    assert {
        len([pair for pair in pairs if pair["task_id"] == task["id"]]) for task in tasks
    } == {2}
    assert all(
        sorted(pair["arm_order"]) == ["control", "internalcot"] for pair in pairs
    )
    assert config["runtime"]["mcp_host"] == "jacobian-remote-mcp"
    assert config["retention"]["publish_internalcot_notes"] is False


def test_visible_messages_exclude_reasoning_final_and_tool_payloads() -> None:
    payload = (
        "\n".join(
            [
                _item({"type": "agent_message", "text": "I found a route."}),
                _item({"type": "reasoning", "text": "private chain"}),
                _item(
                    {
                        "type": "mcp_tool_call",
                        "tool": "math.find",
                        "arguments": {"secret": 1},
                        "result": {"secret": 2},
                    }
                ),
                _item({"type": "agent_message", "text": "Final answer."}),
            ]
        )
        + "\n"
    ).encode()

    messages, prefix_counts = study._visible_messages(payload)

    assert [message["text"] for message in messages] == ["I found a route."]
    assert prefix_counts == [1]
    assert "private chain" not in json.dumps(messages)
    assert "Final answer" not in json.dumps(messages)


def test_internalcot_projection_checks_structure_without_publishing_note_text() -> None:
    workflow = "workflow instructions\n"
    workflow_sha = "sha256:" + hashlib.sha256(workflow.encode()).hexdigest()
    payload = (
        "\n".join(
            [
                _item(
                    {
                        "type": "command_execution",
                        "command": "/bin/bash -lc 'internalcot skill'",
                        "aggregated_output": workflow,
                    }
                ),
                _item(
                    {
                        "type": "command_execution",
                        "command": "/bin/bash -lc \"internalcot note 'secret derivation before'\"",
                        "aggregated_output": "internalcot> secret derivation before\n",
                    }
                ),
                _item({"type": "mcp_tool_call", "tool": "math.run"}),
                _item(
                    {
                        "type": "command_execution",
                        "command": "/bin/bash -lc 'printf result'",
                        "aggregated_output": "result",
                    }
                ),
                _item(
                    {
                        "type": "command_execution",
                        "command": "/bin/bash -lc \"internalcot note 'secret final verification'\"",
                        "aggregated_output": "internalcot> secret final verification\n",
                    }
                ),
                _item({"type": "agent_message", "text": "done"}),
            ]
        )
        + "\n"
        + json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 4,
                    "reasoning_output_tokens": 3,
                },
            }
        )
        + "\n"
    ).encode()

    notes, adherence, behavior = study._intervention_trace(
        payload, expected_workflow_sha256=workflow_sha
    )

    assert adherence["adherent"] is True
    assert adherence["successful_note_count"] == 2
    assert study._note_prefix_counts(payload) == [1]
    assert behavior["host_command_count"] == 4
    assert behavior["reasoning_output_tokens"] == 3
    assert "secret derivation" in str(notes[0]["text"])
    assert "text" not in adherence
    assert "text" not in behavior


def test_internalcot_adherence_fails_closed_on_bad_order_or_workflow() -> None:
    payload = (
        "\n".join(
            [
                _item(
                    {
                        "type": "command_execution",
                        "command": "internalcot skill",
                        "aggregated_output": "wrong",
                    }
                ),
                _item({"type": "mcp_tool_call", "tool": "math.find"}),
                _item(
                    {
                        "type": "command_execution",
                        "command": "internalcot note 'late'",
                        "aggregated_output": "internalcot> late",
                    }
                ),
                _item({"type": "agent_message", "text": "done"}),
            ]
        )
        + "\n"
    ).encode()

    _, adherence, _ = study._intervention_trace(
        payload, expected_workflow_sha256="sha256:" + "0" * 64
    )

    assert adherence["adherent"] is False
    assert adherence["official_skill_loaded"] is False
    assert adherence["first_note_before_substantive"] is False


def test_current_server_evidence_is_bound_without_assurance_inference() -> None:
    digest = "sha256:" + "3" * 64
    payload = (
        "INFO MCP capability attempt request_digest=cccccccccccccccc "
        "trace_digest=cccccccc trace_source=request_id "
        "capability_id=matrix.normal_form.hermite.verify capability_version=1 "
        "execution_status=COMPLETED verification_record_uri_present=True "
        "diagnostic_codes=none attempt_duration_ms=4.5 operation_runtime_ms=2 "
        f"response_bytes=120 argument_digest={digest}"
    )

    events, coverage = study._server_events(payload)

    assert coverage == {"candidates": 1, "recorded": 1}
    assert events[0]["assurance"] is None
    assert events[0]["verification_record_uri_present"] is True
    assert study._checker_state(events) == "ACCEPTED_ONLY"


def test_checker_without_bound_evidence_fails_closed() -> None:
    event = {
        "kind": "CAPABILITY_ATTEMPT",
        "capability_id": "matrix.normal_form.hermite.verify",
        "execution_status": "COMPLETED",
        "assurance": None,
        "verification_record_uri_present": False,
        "diagnostic_codes": [],
    }

    assert study._checker_label([event]) == "REJECTED_UNRECOVERED"


def test_condition_features_use_arm_specific_visible_source() -> None:
    control = study.Row(
        "task", "PASS", {"xy": 1.0}, {"b:count": 2.0}, {"tau:event_count": 1.0}
    )
    treatment = study.Row(
        "task",
        "PASS",
        {"xy": 1.0},
        {"b_star:count": 3.0},
        {"tau:event_count": 1.0},
        arm="internalcot",
    )

    assert "b:count" not in study._condition_features(control, "x+y+tau_tools")
    assert study._condition_features(control, "x+y+b+tau_tools")["b:count"] == 2.0
    assert (
        study._condition_features(treatment, "x+y+b+tau_tools")["b_star:count"] == 3.0
    )


def test_family_predictions_hold_out_complete_family(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        study.Row("a-1", "A", {"x": 0.0}, {}, {}, "family-a"),
        study.Row("a-2", "B", {"x": 0.1}, {}, {}, "family-a"),
        study.Row("b-1", "A", {"x": 1.0}, {}, {}, "family-b"),
        study.Row("c-1", "B", {"x": 2.0}, {}, {}, "family-c"),
    ]
    observed: list[tuple[str, set[str]]] = []

    def fake_predict(
        train: list[study.Row],
        test: study.Row,
        condition: str,
        *,
        tau_groups: frozenset[str] | None = None,
    ) -> str:
        del condition, tau_groups
        families = {row.family_id for row in train}
        observed.append((test.family_id, families))
        assert test.family_id not in families
        return train[0].label

    monkeypatch.setattr(study, "_predict", fake_predict)
    predictions = study._family_predictions(rows, "x+y+tau_tools")

    assert len(predictions) == len(rows)
    assert len(observed) == len(rows)


def test_paired_behavior_uses_treatment_minus_control_and_task_bootstrap() -> None:
    projections = []
    for task_index in range(4):
        for repetition in range(2):
            pair = f"task-{task_index}--r{repetition}"
            for arm, value in (("control", 1.0), ("internalcot", 2.0)):
                projections.append(
                    {
                        "pair_id": pair,
                        "arm": arm,
                        "task_id": f"task-{task_index}",
                        "behavior_metrics": {"jacobian_call_count": value},
                    }
                )

    report = study._paired_behavior(projections, seed=9, repetitions=20)

    assert report["jacobian_call_count"]["treatment_minus_control_mean"] == 1.0
    assert report["jacobian_call_count"]["task_bootstrap_95"] == {
        "lower_95": 1.0,
        "upper_95": 1.0,
    }


def test_server_command_uses_current_remote_host() -> None:
    command = study._server_command(
        state_dir=Path("/tmp/state"), port=8123, trial_id="trial"
    )

    assert "jacobian.adapters.mcp.remote_cli" in command[2]
    assert "--allow-anonymous" in command
