from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from benchmarks.tooling import symbolic_coordination_trajectory as st
from jsonschema import Draft202012Validator

from jacobian.eval.telemetry import parse_agent_transcript

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "symbolic_coordination_trajectory"
    / "adversarial-v1.json"
)
SCHEMA = (
    Path(__file__).parents[1]
    / "schemas"
    / "symbolic-coordination-trajectory-v1.schema.json"
)
TASK_ID = "symbolic-coordination-near-miss-01"


def _fixtures() -> dict[str, dict[str, Any]]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1"
    return cast(dict[str, dict[str, Any]], payload["cases"])


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(st._canonical_bytes(value))


def _verifier(reward: float) -> dict[str, Any]:
    return {
        "execution_status": "COMPLETED",
        "mathematical_observation": "ACCEPTED" if reward == 1.0 else "REJECTED",
        "reward": {
            "correctness": reward,
            "evidence_validity": reward,
            "scope_accuracy": reward,
            "assurance_calibration": reward,
            "input_binding": reward,
            "artifact_binding": reward,
            "protocol_compliance": reward,
            "false_certification": False,
            "reward": reward,
        },
        "verifier_workspace_outside_model_workspace": True,
    }


def _submission(conclusion: str, *, marker: str = "initial") -> dict[str, Any]:
    return {
        "conclusion": conclusion,
        "result": {"verdict": "UNKNOWN", "marker": marker},
        "claimed_assurance": "COMPUTED",
        "scope": "EXACT_TWO_SIDED_COMPOSITION_OVER_QQ:" + TASK_ID,
        "completeness": "COMPLETE",
    }


def _submission_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": [
            "conclusion",
            "result",
            "claimed_assurance",
            "scope",
            "completeness",
        ],
        "properties": {
            "conclusion": {"enum": ["TRUE", "FALSE", "UNKNOWN"]},
            "result": {
                "type": "object",
                "required": ["verdict", "marker"],
                "properties": {
                    "verdict": {"type": "string"},
                    "marker": {"type": "string"},
                },
            },
            "claimed_assurance": {"type": "string"},
            "scope": {"type": "string"},
            "completeness": {"type": "string"},
        },
    }


def _index(root: Path) -> None:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "artifact-index.json":
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "digest": st._digest_file(path),
                }
            )
    _write_json(root / "artifact-index.json", {"schema_version": "1", "files": files})


def _materialize_run(
    tmp_path: Path,
    scenario: dict[str, Any],
    *,
    extra_events: list[dict[str, Any]] | None = None,
) -> Path:
    condition = scenario.get("condition", "A")
    root = tmp_path / "run"
    root.mkdir()
    primary_prompt = b"primary\n"
    audit_prompt = b"audit\n"
    (root / "primary-prompt.txt").write_bytes(primary_prompt)
    (root / "audit-prompt.txt").write_bytes(audit_prompt)
    schema = _submission_schema()
    input_payload = {"case_id": TASK_ID, "family": "perturbed-near-miss"}
    instruction = b"assess the exact claim\n"
    workspace = root / condition / "workspace"
    workspace.mkdir(parents=True)
    _write_json(workspace / "input.json", input_payload)
    (workspace / "instruction.md").write_bytes(instruction)
    _write_json(workspace / "submission_schema.json", schema)
    public_hashes = {
        "input.json": st._digest_file(workspace / "input.json"),
        "instruction.md": st._digest_file(workspace / "instruction.md"),
        "submission_schema.json": st._digest_file(workspace / "submission_schema.json"),
    }
    snapshot_body = {
        "schema_version": "1",
        "task": {"id": TASK_ID, "public_file_hashes": public_hashes},
        "source": {"revision": "1" * 40},
        "model": {"slug": "gpt-5.3-codex-spark"},
        "reasoning_effort": "medium",
        "prompts": {
            "primary_digest": st._digest_bytes(primary_prompt),
            "audit_digest": st._digest_bytes(audit_prompt),
        },
        "conditions": {
            "A": {"reasoning_log_mode": "OFF"},
            "B": {"reasoning_log_mode": "REQUIRED"},
            "C": {"reasoning_log_mode": "REQUIRED"},
        },
    }
    snapshot_id = st._digest_bytes(st._canonical_bytes(snapshot_body))
    _write_json(
        root / "runtime-snapshot.json", {**snapshot_body, "snapshot_id": snapshot_id}
    )
    events = list(scenario.get("events", []))
    events.extend(extra_events or [])
    if not scenario.get("omit_usage"):
        events.append(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 100,
                    "cached_input_tokens": 25,
                    "cache_write_input_tokens": 0,
                    "output_tokens": 20,
                    "reasoning_output_tokens": 5,
                },
            }
        )
    raw_jsonl = scenario.get("raw_jsonl")
    primary_path = root / condition / "primary.codex.jsonl"
    if isinstance(raw_jsonl, str):
        primary_path.write_text(raw_jsonl, encoding="utf-8")
    else:
        primary_path.write_text(
            "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
        )
    _write_json(
        root / condition / "primary.telemetry.json",
        parse_agent_transcript(primary_path),
    )
    _write_json(root / condition / "primary.timing.json", {"elapsed_seconds": 1.25})
    if condition in {"B", "C"}:
        _write_json(
            root / condition / "reasoning-logs" / "index.json",
            {"status": "EXPORTED", "runs": []},
        )
    final_conclusion = scenario.get("final_conclusion", "UNKNOWN")
    initial_submission = _submission(final_conclusion)
    final_submission = _submission(
        final_conclusion,
        marker="final" if scenario.get("revision_applied") else "initial",
    )
    for stage, submission in (
        ("pre-audit", initial_submission),
        ("final", final_submission),
    ):
        _write_json(root / condition / stage / "submission.json", submission)
        _write_json(
            root / condition / stage / "evidence" / "certificate.json",
            {"stage": stage if scenario.get("revision_applied") else "same"},
        )
    if condition == "C":
        audit_events = [
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 30,
                    "output_tokens": 10,
                    "reasoning_output_tokens": 2,
                },
            }
        ]
        audit_path = root / condition / "audit.codex.jsonl"
        audit_path.write_text(
            "".join(json.dumps(event) + "\n" for event in audit_events),
            encoding="utf-8",
        )
        _write_json(
            root / condition / "audit.telemetry.json",
            parse_agent_transcript(audit_path),
        )
        _write_json(root / condition / "audit.timing.json", {"elapsed_seconds": 0.75})
    initial_reward = scenario.get("initial_reward", scenario.get("final_reward", 1.0))
    final_reward = scenario.get("final_reward", 1.0)
    initial_verifier = (
        _verifier(float(initial_reward)) if initial_reward is not None else None
    )
    final_verifier = (
        _verifier(float(final_reward)) if final_reward is not None else None
    )
    if initial_verifier is not None:
        _write_json(root / condition / "initial-verifier-result.json", initial_verifier)
    if final_verifier is not None:
        _write_json(root / condition / "verifier-result.json", final_verifier)
    failures = list(scenario.get("infrastructure_failures", []))
    status = "INCOMPLETE" if failures else "COMPLETE"
    condition_result = {
        "schema_version": "1",
        "condition": condition,
        "snapshot_id": snapshot_id,
        "infrastructure_status": status,
        "infrastructure_failures": failures,
        "model": "gpt-5.3-codex-spark",
        "reasoning_effort": "medium",
        "revision_applied": scenario.get("revision_applied")
        if condition == "C"
        else None,
        "initial_verifier": initial_verifier,
        "verifier": final_verifier,
    }
    _write_json(root / condition / "condition-result.json", condition_result)
    _write_json(
        root / "run-result.json",
        {
            "schema_version": "1",
            "status": status,
            "snapshot_id": snapshot_id,
            "task": TASK_ID,
            "conditions": [condition_result],
        },
    )
    _index(root)
    return root


def _one(tmp_path: Path, name: str) -> st.RunTelemetry:
    records = st.analyze_run(_materialize_run(tmp_path, _fixtures()[name]))
    assert len(records) == 1
    return records[0]


def test_adversarial_fixture_contract_is_complete() -> None:
    assert set(_fixtures()) == {
        "duplicated_calls",
        "missing_checker",
        "timeout_overclaim",
        "stale_artifact",
        "artifact_substitution",
        "malformed_logs",
        "missing_token_usage",
        "audit_repair",
        "audit_regression",
        "audit_unchanged_failure",
        "audit_already_correct",
        "audit_incomplete",
        "incomplete_run",
    }


def test_counts_schema_valid_executable_failed_and_repeated_calls(
    tmp_path: Path,
) -> None:
    record = _one(tmp_path, "duplicated_calls")

    assert record.calls.invocation_calls == 2
    assert record.calls.schema_valid_calls == 2
    assert record.calls.executable_calls == 2
    assert record.calls.failed_calls == 0
    assert record.calls.repeated_calls == 1
    assert record.calls.task_irrelevant_calls == 0
    assert record.usage.primary.total_tokens == 120
    assert record.wall_time.total_seconds == 1.25


def test_candidate_without_applicable_checker_is_a_protocol_violation(
    tmp_path: Path,
) -> None:
    record = _one(tmp_path, "missing_checker")

    assert record.calls.candidate_or_witness_productions == 1
    assert record.calls.missing_applicable_checker == 1
    assert "MISSING_APPLICABLE_CHECKER" in record.classification.protocol_violations


def test_timeout_overclaim_remains_separate_from_infrastructure(tmp_path: Path) -> None:
    record = _one(tmp_path, "timeout_overclaim")

    assert record.infrastructure_status == "COMPLETE"
    assert record.search_outcomes.timeout_count == 1
    assert record.search_outcomes.incomplete_count == 1
    assert record.search_outcomes.unresolved_nonconclusive_count == 1
    assert record.search_outcomes.final_claim_improperly_escalates is True
    assert "UNRESOLVED_NONCONCLUSIVE_OVERCLAIM" in (
        record.classification.protocol_violations
    )


@pytest.mark.parametrize(
    ("fixture", "field", "violation"),
    [
        ("stale_artifact", "stale_binding_failure_count", "STALE_ARTIFACT_BINDING"),
        (
            "artifact_substitution",
            "substitution_failure_count",
            "ARTIFACT_SUBSTITUTION",
        ),
    ],
)
def test_typed_artifact_failure_codes_are_classified(
    tmp_path: Path, fixture: str, field: str, violation: str
) -> None:
    record = _one(tmp_path, fixture)

    assert getattr(record.artifact_flow, field) == 1
    assert violation in record.classification.protocol_violations


def test_malformed_jsonl_fails_closed(tmp_path: Path) -> None:
    root = _materialize_run(tmp_path, _fixtures()["malformed_logs"])

    with pytest.raises(st.TrajectoryTelemetryError, match="malformed A primary JSONL"):
        st.analyze_run(root)


def test_missing_token_usage_is_unavailable_not_estimated(tmp_path: Path) -> None:
    record = _one(tmp_path, "missing_token_usage")

    assert record.usage.primary.availability == "UNAVAILABLE"
    assert record.usage.primary.total_tokens is None
    assert record.infrastructure_status == "INCOMPLETE"
    assert "INCOMPLETE_INFRASTRUCTURE" in record.classification.protocol_violations


@pytest.mark.parametrize(
    ("fixture", "classification"),
    [
        ("audit_repair", "REPAIR"),
        ("audit_regression", "REGRESSION"),
        ("audit_unchanged_failure", "UNCHANGED_FAILURE"),
        ("audit_already_correct", "ALREADY_CORRECT"),
        ("audit_incomplete", "INCOMPLETE"),
    ],
)
def test_audit_revision_uses_before_and_after_verifier_results(
    tmp_path: Path, fixture: str, classification: str
) -> None:
    record = _one(tmp_path, fixture)

    assert record.audit.revision_applied is (
        fixture in {"audit_repair", "audit_regression"}
    )
    assert record.audit.classification == classification
    assert record.classification.successful_recovery is (classification == "REPAIR")
    assert record.usage.audit is not None
    assert record.wall_time.audit_seconds == 0.75


def test_incomplete_run_preserves_missing_verifier_as_incomplete(
    tmp_path: Path,
) -> None:
    record = _one(tmp_path, "incomplete_run")

    assert record.infrastructure_status == "INCOMPLETE"
    assert record.audit.final_verifier is None
    assert record.audit.classification == "NOT_APPLICABLE"


def test_artifact_index_tampering_and_source_inconsistency_fail_closed(
    tmp_path: Path,
) -> None:
    root = _materialize_run(tmp_path, _fixtures()["duplicated_calls"])
    (root / "A" / "primary.timing.json").write_text(
        '{"elapsed_seconds":9}\n', encoding="utf-8"
    )

    with pytest.raises(st.TrajectoryTelemetryError, match="artifact mismatch"):
        st.analyze_run(root)


def test_checker_handoff_recovery_bounded_exhaustion_and_irrelevance() -> None:
    artifact = "artifact://sha256/" + "a" * 64

    def event(
        capability_id: str, response: dict[str, Any], payload: object
    ) -> dict[str, Any]:
        return {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "tool": "capability.invoke",
                "arguments": {"capability_id": capability_id, "payload": payload},
                "status": "completed",
                "result": {
                    "isError": response["execution"]["status"] != "COMPLETED",
                    "content": [{"type": "text", "text": json.dumps(response)}],
                },
            },
        }

    events = [
        event(
            "polynomial.map.inverse.candidate_synthesize",
            {
                "execution": {"status": "COMPLETED"},
                "output": {"candidate_inverse_map": {}, "status": "FOUND"},
                "artifact_uris": [artifact],
                "completeness": {"status": "COMPLETE"},
            },
            {},
        ),
        event(
            "polynomial.map.inverse.verify",
            {
                "execution": {"status": "COMPLETED"},
                "output": {"status": "VERIFIED"},
                "artifact_uris": [],
                "completeness": {"status": "COMPLETE"},
            },
            {"candidate_uri": artifact},
        ),
        event(
            "polynomial.map.collision.search",
            {
                "execution": {"status": "TIMEOUT"},
                "output": {"status": "TIMEOUT"},
                "artifact_uris": [],
                "completeness": {"status": "UNKNOWN"},
            },
            {},
        ),
        event(
            "polynomial.map.collision.search",
            {
                "execution": {"status": "COMPLETED"},
                "output": {"stop_reason": "GRID_EXHAUSTED"},
                "artifact_uris": [],
                "completeness": {"status": "COMPLETE"},
            },
            {},
        ),
        event(
            "graph.search.atlas",
            {
                "execution": {"status": "COMPLETED"},
                "output": {"status": "FOUND"},
                "artifact_uris": [],
                "completeness": {"status": "COMPLETE"},
            },
            {},
        ),
    ]
    calls, recovered = st._capability_calls(events, "perturbed-near-miss")
    final = st.SubmissionState(
        present=True,
        schema_valid=True,
        digest="sha256:" + "b" * 64,
        conclusion="TRUE",
        verdict="VALID_TWO_SIDED_INVERSE",
        claimed_assurance="COMPUTED",
        scope="scope",
        completeness="COMPLETE",
    )
    outcomes = st._search_outcomes(calls, final)
    flow = st._artifact_flow(calls, st._invoke_items(events), _verifier_scores())
    metrics = st._call_metrics(
        {"mcp_calls": ["capability.invoke"] * len(events), "shell_calls": []},
        calls,
        recovered,
    )

    assert calls[0].checker_followed is True
    assert metrics.producer_calls == 3
    assert metrics.checker_calls == 1
    assert flow.handoff_count == 1
    assert flow.reused_uri_count == 1
    assert recovered == 1
    assert outcomes.bounded_exhaustion_count == 1
    assert outcomes.unresolved_nonconclusive_count == 0
    assert outcomes.final_claim_improperly_escalates is False
    assert calls[-1].task_relevant is False


def test_failed_producer_and_failed_checker_do_not_establish_handoff() -> None:
    def event(
        capability_id: str, status: str, output: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "tool": "capability.invoke",
                "arguments": {"capability_id": capability_id, "payload": {}},
                "status": "completed",
                "result": {
                    "isError": status != "COMPLETED",
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "execution": {"status": status},
                                    "output": output,
                                    "artifact_uris": [],
                                    "completeness": {"status": "UNKNOWN"},
                                }
                            ),
                        }
                    ],
                },
            },
        }

    failed_producer, _ = st._capability_calls(
        [
            event(
                "polynomial.map.inverse.candidate_synthesize",
                "ERROR",
                {"candidate_inverse_map": {}, "status": "FOUND"},
            )
        ],
        "perturbed-near-miss",
    )
    assert failed_producer[0].produced is False
    assert failed_producer[0].checker_followed is None

    failed_checker, _ = st._capability_calls(
        [
            event(
                "polynomial.map.inverse.candidate_synthesize",
                "COMPLETED",
                {"candidate_inverse_map": {}, "status": "FOUND"},
            ),
            event(
                "polynomial.map.inverse.verify",
                "ERROR",
                {"status": "VERIFIED"},
            ),
        ],
        "perturbed-near-miss",
    )
    assert failed_checker[0].produced is True
    assert failed_checker[0].checker_followed is False


def _verifier_scores() -> st.VerifierScores:
    return st.VerifierScores(
        execution_status="COMPLETED",
        mathematical_observation="ACCEPTED",
        correctness=1.0,
        evidence_validity=1.0,
        scope_accuracy=1.0,
        assurance_calibration=1.0,
        input_binding=1.0,
        artifact_binding=1.0,
        protocol_compliance=1.0,
        false_certification=False,
        reward=1.0,
    )


def test_reasoning_protocol_counts_bytes_entries_and_never_estimates_tokens(
    tmp_path: Path,
) -> None:
    condition_root = tmp_path / "B" / "reasoning-logs"
    condition_root.mkdir(parents=True)
    log = condition_root / "run.jsonl"
    log.write_text(
        "".join(json.dumps({"phase": phase}) + "\n" for phase in st.REASONING_PHASES),
        encoding="utf-8",
    )
    _write_json(
        condition_root / "index.json",
        {
            "status": "EXPORTED",
            "runs": [
                {
                    "path": "run.jsonl",
                    "event_count": 4,
                    "digest": st._digest_file(log),
                }
            ],
        },
    )
    telemetry = {
        "reasoning_protocol": {
            "status": "COMPLETE",
            "plan_count": 1,
            "before_tool_count": 1,
            "after_tool_count": 1,
            "final_count": 1,
        },
        "successful_tool_calls": ["reasoning.write"] * 4,
    }

    record = st._reasoning(
        tmp_path,
        "B",
        {"reasoning_log_mode": "REQUIRED"},
        telemetry,
    )

    assert record.compliance == "COMPLETE"
    assert record.log_entries == 4
    assert record.log_bytes == log.stat().st_size
    assert record.token_overhead_availability == "UNAVAILABLE"
    assert record.token_overhead_tokens is None


def test_bundle_aggregates_dimensions_without_collapsing_verifier_scores(
    tmp_path: Path,
) -> None:
    root = _materialize_run(tmp_path, _fixtures()["duplicated_calls"])
    bundle = st.build_bundle([root])

    assert bundle.causal_claim_authorized is False
    assert bundle.aggregates.per_task[0].correctness_mean == 1.0
    assert bundle.aggregates.per_task[0].evidence_validity_mean == 1.0
    assert bundle.aggregates.per_task[0].scope_accuracy_mean == 1.0
    assert bundle.aggregates.per_task[0].assurance_calibration_mean == 1.0
    assert bundle.aggregates.per_task[0].input_binding_mean == 1.0
    assert bundle.aggregates.per_task[0].artifact_binding_mean == 1.0
    assert bundle.aggregates.per_task[0].protocol_compliance_mean == 1.0
    assert bundle.aggregates.per_task[0].reward_mean == 1.0
    assert bundle.aggregates.per_task[0].invocation_calls == 2
    assert bundle.aggregates.per_task[0].repeated_calls == 1
    assert bundle.aggregates.per_task[0].total_tokens == 120
    assert bundle.aggregates.per_task[0].wall_seconds == 1.25
    assert bundle.aggregates.per_task[0].reasoning_log_entries == 0
    assert bundle.aggregates.overall[-1].infrastructure_complete == 1
    tables = st.render_tables(bundle)
    assert "Per task: verifier and resources" in tables
    assert "Per task: calls" in tables
    assert "Per task: search, artifacts, reasoning, and audit" in tables


def test_aggregate_tokens_and_wall_include_applicable_audit_stage(
    tmp_path: Path,
) -> None:
    root = _materialize_run(tmp_path, _fixtures()["audit_repair"])
    row = st.build_bundle([root]).aggregates.per_task[0]

    assert row.exact_token_run_count == 1
    assert row.total_tokens == 160
    assert row.exact_wall_run_count == 1
    assert row.wall_seconds == 2.0
    assert row.reasoning_required_run_count == 1


def test_committed_telemetry_schema_matches_typed_model_and_accepts_bundle(
    tmp_path: Path,
) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    root = _materialize_run(tmp_path, _fixtures()["duplicated_calls"])
    payload = st.build_bundle([root]).model_dump(mode="json")

    assert schema == st.TelemetryBundle.model_json_schema()
    Draft202012Validator(schema).validate(payload)
