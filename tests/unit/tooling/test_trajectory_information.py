from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from benchmarks.tooling import trajectory_information as study

REPOSITORY_ROOT = Path(__file__).parents[3]


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


def test_current_server_evidence_projection_does_not_infer_assurance() -> None:
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
    assert study._checker_label(events) == "SUCCESS_WITHOUT_REJECTION"


def test_checker_without_assurance_or_evidence_fails_closed() -> None:
    event = {
        "kind": "CAPABILITY_ATTEMPT",
        "capability_id": "matrix.normal_form.hermite.verify",
        "execution_status": "COMPLETED",
        "assurance": None,
        "verification_record_uri_present": False,
        "diagnostic_codes": [],
    }

    assert study._checker_label([event]) == "REJECTED_UNRECOVERED"


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
        train: list[study.Row] | tuple[study.Row, ...],
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

    predictions = study._family_predictions(rows, "x+y")

    assert len(predictions) == len(rows)
    assert len(observed) == len(rows)


def test_tau_field_groups_are_exhaustive_for_projected_features() -> None:
    events = [
        {
            "kind": "CAPABILITY_ATTEMPT",
            "request_digest": "a" * 16,
            "capability_id": "matrix.determinant.verify",
            "execution_status": "COMPLETED",
            "assurance": "VERIFIED",
            "diagnostic_codes": [],
            "attempt_duration_ms": 2.0,
            "response_bytes": 20,
            "argument_digest": "sha256:" + "1" * 64,
        },
        {
            "kind": "TOOL_CALL",
            "tool": "math.run",
            "status": "success",
            "request_digest": "a" * 16,
            "duration_ms": 3.0,
            "response_bytes": 30,
            "argument_digest": "sha256:" + "1" * 64,
        },
    ]

    features = study._tau_features(events)
    groups = {study._tau_field_group(name) for name in features}

    assert groups == set(study._TAU_FIELD_GROUPS)
    assert features["tau:capability:matrix.determinant.verify"] == 1.0
    assert features["tau:domain:matrix"] == 1.0


def test_checker_and_tool_failure_recovery_are_separate() -> None:
    rejected = {
        "kind": "CAPABILITY_ATTEMPT",
        "capability_id": "matrix.determinant.verify",
        "execution_status": "COMPLETED",
        "assurance": "COMPUTED",
        "diagnostic_codes": ["CANDIDATE_REJECTED"],
    }
    recovered = {
        **rejected,
        "assurance": "VERIFIED",
        "diagnostic_codes": [],
    }

    assert study._checker_state([rejected]) == "REJECTED"
    assert study._recovery_state([rejected]) == "UNRECOVERED"
    assert study._checker_state([rejected, recovered]) == "REJECTED"
    assert study._recovery_state([rejected, recovered]) == "RECOVERED"


def test_v2_config_freezes_unseen_complete_families() -> None:
    v1 = json.loads(
        (
            REPOSITORY_ROOT / "benchmarks/config/trajectory-information-v1.json"
        ).read_text()
    )
    v2 = json.loads(
        (
            REPOSITORY_ROOT / "benchmarks/config/trajectory-information-v2.json"
        ).read_text()
    )
    v1_ids = {item["id"] for item in v1["dataset"]["tasks"]}
    v2_ids = {item["id"] for item in v2["dataset"]["tasks"]}
    families: dict[str, set[str]] = {}
    for item in v2["dataset"]["tasks"]:
        families.setdefault(item["family"], set()).add(item["id"])

    assert v1_ids.isdisjoint(v2_ids)
    assert len(v2_ids) == 12
    assert {len(tasks) for tasks in families.values()} == {3}
    assert v2["runtime"]["repetitions_per_task"] == 2
    assert v2["modeling"]["transductive"] is False


def test_heldout_summary_and_tau_ablation_are_family_inductive() -> None:
    rows = [
        study.Row(
            task_id=f"task-{family}-{index}",
            label="PASS" if index == 0 else "FAIL",
            x_y={"xy:index": float(index)},
            b={"b:message_count": float(index)},
            tau={
                "tau:event_count": float(index + 1),
                "tau:capability:matrix.rank": float(index),
                "tau:execution:COMPLETED": 1.0,
                "tau:duration_log1p_sum": 1.0,
                "tau:request_digest_available": 1.0,
            },
            family_id=f"family-{family}",
        )
        for family in range(4)
        for index in range(2)
    ]
    all_rows = dict.fromkeys(study._HELDOUT_TARGETS, rows)

    results, eligible, predictions = study._summarize_heldout_diagnostics(
        all_rows,
        {"diagnostic_requires_at_least_classes": 2},
        seed=7,
        bootstrap_repetitions=20,
    )
    ablation = study._tau_ablation_report(all_rows, results, eligible)

    assert eligible == list(study._HELDOUT_TARGETS)
    assert set(predictions["terminal_verifier_success"]) == set(study._CONDITIONS)
    assert set(ablation) == set(study._TAU_FIELD_GROUPS)
    assert results["terminal_verifier_success"]["family_count"] == 4
    assert results["terminal_verifier_success"]["conditions"]["x+y"][
        "task_bootstrap_95"
    ].keys() == {"lower_95", "upper_95"}


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


def test_committed_report_is_bounded_and_noncausal() -> None:
    report_path = (
        REPOSITORY_ROOT
        / "benchmarks/evidence/observable-trajectory-information-v1/report.json"
    )
    report = json.loads(report_path.read_text())

    assert report["study_id"] == "observable-trajectory-information-v1"
    assert report["dataset"]["completed_trial_count"] == 12
    assert report["analysis"] == {
        "held_out": False,
        "metric_semantics": (
            "Transductive exact-signature purity over fixed corpus-independent "
            "presence bins; descriptive only."
        ),
        "mode": "FROZEN_SIMPLEST_DEFENSIBLE_FALLBACK",
        "transductive": True,
    }
    assert report["decision"] == "INCONCLUSIVE_RESEARCH_ONLY"
    assert report["causal_claim_authorized"] is False
    assert report["retention"]["publish_hidden_reasoning"] is False
    assert report["retention"]["publish_agent_messages"] is False
    assert report["retention"]["publish_tool_arguments_or_results"] is False


def test_committed_heldout_report_is_inductive_bounded_and_fail_closed() -> None:
    report_path = (
        REPOSITORY_ROOT
        / "benchmarks/evidence/observable-trajectory-information-v2/report.json"
    )
    report = json.loads(report_path.read_text())

    assert report["study_id"] == "observable-trajectory-information-heldout-v2"
    assert report["analysis"]["held_out"] is True
    assert report["analysis"]["transductive"] is False
    assert report["dataset"]["completed_trial_count"] == 24
    assert report["dataset"]["eligible"] is False
    assert report["decision"] == "INCONCLUSIVE_RESEARCH_ONLY"
    assert report["event_coverage"]["checker_rejections"] == 1
    assert report["event_coverage"]["no_tool_trajectories"] == 1
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", report["collector_sha256"])
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", report["analyzer_sha256"])
    assert report["retention"]["publish_hidden_reasoning"] is False
    assert report["retention"]["publish_agent_messages"] is False
    assert report["retention"]["publish_tool_arguments_or_results"] is False
    assert all(
        set(projection)
        == {
            "command_status",
            "family",
            "labels",
            "repetition",
            "server_event_coverage",
            "status",
            "summary_metrics",
            "task_id",
            "tool_metrics",
            "trial_id",
        }
        for projection in report["projections"]
    )
    rendered = json.dumps(report)
    for forbidden in (
        '"arguments":',
        '"prompt":',
        '"raw_artifacts":',
        '"reasoning_content":',
        '"text":',
        '"workspace_artifacts":',
    ):
        assert forbidden not in rendered
