from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from benchmarks.tooling import observation_results
from benchmarks.tooling.observation_results import (
    build_observation_evidence,
    build_routing_observation,
    compare_evidence,
    render_markdown,
    resolved_config_failures,
)


def _evidence(condition: str, correctness: list[float]) -> dict:
    trials = []
    for repetition, reward in enumerate(correctness):
        trials.append(
            {
                "task": "case",
                "task_digest": "sha256:" + "a" * 64,
                "repetition": repetition,
                "rewards": {
                    "correctness": reward,
                    "evidence_validity": reward,
                    "scope_accuracy": 1.0,
                    "assurance_calibration": 1.0,
                    "reward": reward,
                },
                "false_certification": False,
                "tokens": {"input": 10, "output": 5},
                "cost_usd": 0.01,
                "agent_seconds": 2.0,
            }
        )
    return {
        "schema_version": "1",
        "evidence_class": "workflow-observation",
        "status": "VALID",
        "causal_claim_authorized": False,
        "source_sha": "a" * 40,
        "dataset": "agent-workflow-v1",
        "condition": condition,
        "job": {
            "path": "job.json",
            "digest": "sha256:" + "c" * 64,
            "comparison_signature": "sha256:" + "b" * 64,
            "n_attempts": len(correctness),
        },
        "runtime_snapshot": {},
        "fixed_invariants": {
            "model": "model",
            "tasks": [{"task": "case", "digest": "sha256:" + "a" * 64}],
            "sampling_seed": None,
            "sampling_deterministic": False,
        },
        "result": {"path": "result.json", "digest": "sha256:" + "d" * 64},
        "trials": trials,
        "validation_failures": [],
    }


def test_paired_report_keeps_public_claim_boundary() -> None:
    report = compare_evidence(
        _evidence("control", [0.0, 1.0]), _evidence("treatment", [1.0, 1.0])
    )

    assert report["status"] == "VALID"
    assert report["causal_claim_authorized"] is False
    assert report["metrics"]["correctness"]["paired_delta"] == 0.5
    assert (
        report["metrics"]["correctness"]["interpretation"] == "descriptive-small-sample"
    )
    assert "does not itself authorize a causal" in render_markdown(report)


def test_comparison_rejects_invariant_drift() -> None:
    control = _evidence("control", [1.0])
    treatment = deepcopy(_evidence("treatment", [1.0]))
    treatment["fixed_invariants"]["model"] = "different"

    report = compare_evidence(control, treatment)

    assert report["status"] == "INVALID"
    assert "fixed invariants differ" in report["validation_failures"]


def test_comparison_rejects_unpaired_repetitions() -> None:
    report = compare_evidence(
        _evidence("control", [1.0, 1.0]), _evidence("treatment", [1.0])
    )

    assert report["status"] == "INVALID"
    assert (
        "control/treatment trials do not pair exactly" in report["validation_failures"]
    )


def test_comparison_rejects_duplicate_pair_keys() -> None:
    control = _evidence("control", [1.0])
    control["trials"].append(deepcopy(control["trials"][0]))

    report = compare_evidence(control, _evidence("treatment", [1.0]))

    assert report["status"] == "INVALID"
    assert "duplicate" in " ".join(report["validation_failures"])


def test_comparison_derives_heldout_class_from_both_inputs() -> None:
    control = _evidence("C1", [1.0])
    treatment = _evidence("C2", [1.0])
    control["evidence_class"] = "held-out-comparative-evaluation"
    treatment["evidence_class"] = "held-out-comparative-evaluation"

    report = compare_evidence(control, treatment)

    assert report["evidence_class"] == "held-out-comparison"
    assert report["status"] == "VALID"


def test_observation_normalization_binds_repetitions_and_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(observation_results, "task_digest", lambda _path: "a" * 64)
    monkeypatch.setattr(observation_results, "_git_sha", lambda: "b" * 40)
    job = {
        "jobs_dir": str(tmp_path / "jobs"),
        "n_attempts": 1,
        "timeout_multiplier": 1,
        "orchestrator": {"type": "local", "n_concurrent_trials": 1},
        "environment": {"type": "docker"},
        "agents": [{"name": "codex"}],
        "datasets": [
            {
                "path": "benchmarks/datasets/agent-workflow-v1",
                "task_names": ["graph-counterexample"],
            }
        ],
    }
    job_path = tmp_path / "job.json"
    job_path.write_text(json.dumps(job), encoding="utf-8")
    result = {
        "id": "job",
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:01:00Z",
        "n_total_trials": 1,
        "stats": {
            "n_completed_trials": 1,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 0,
            "n_cancelled_trials": 0,
        },
        "trial_results": [
            {
                "task_name": "jacobian/graph-counterexample",
                "task_checksum": "sha256:" + "a" * 64,
                "trial_name": "attempt-0",
                "agent_info": {
                    "name": "codex",
                    "version": "1",
                    "model_info": {"name": "model"},
                },
                "agent_result": {
                    "n_input_tokens": 10,
                    "n_output_tokens": 5,
                    "cost_usd": 0.01,
                },
                "verifier_result": {
                    "rewards": {"correctness": 1.0, "false_certification": 0.0}
                },
                "exception_info": None,
            }
        ],
    }
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")

    evidence, failures = build_observation_evidence(
        dataset="agent-workflow-v1",
        condition="control",
        job_path=job_path,
        jobs_dir=tmp_path,
        result_path=result_path,
    )

    assert failures == []
    assert evidence["status"] == "VALID"
    assert evidence["fixed_invariants"]["model"] == "model"


def _resolved_treatment(tmp_path: Path) -> Path:
    path = tmp_path / "resolved-config.json"
    path.write_text(
        json.dumps(
            {
                "jobs_dir": str(tmp_path / "jobs"),
                "n_attempts": 1,
                "environment": {
                    "type": "docker",
                    "extra_docker_compose": [
                        "benchmarks/config/agent-eval-proxy.compose.yaml",
                        "benchmarks/datasets/agent-workflow-v1/jacobian-observation.compose.yaml",
                    ],
                },
                "agents": [
                    {
                        "name": "codex",
                        "model_name": "model",
                        "mcp_servers": [
                            {
                                "name": "jacobian",
                                "transport": "streamable-http",
                                "url": "http://jacobian:8000/mcp",
                            }
                        ],
                    }
                ],
                "datasets": [
                    {
                        "path": "benchmarks/datasets/agent-workflow-v1",
                        "task_names": ["graph-counterexample"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _routing_result(tmp_path: Path, events: list[dict]) -> tuple[Path, Path]:
    run = tmp_path / "jobs" / "run"
    trial = run / "trial-0"
    (trial / "agent").mkdir(parents=True)
    (trial / "agent" / "codex.txt").write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )
    trial_result = {
        "task_name": "jacobian/graph-counterexample",
        "task_checksum": "sha256:" + "a" * 64,
        "trial_name": "attempt-0",
        "agent_info": {"model_info": {"name": "model"}},
        "agent_result": {},
        "verifier_result": {
            "rewards": {"correctness": 1.0, "false_certification": 0.0}
        },
        "exception_info": None,
    }
    (trial / "result.json").write_text(json.dumps(trial_result), encoding="utf-8")
    result = {
        "id": "run",
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:01:00Z",
        "n_total_trials": 1,
        "stats": {
            "n_completed_trials": 1,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 0,
            "n_cancelled_trials": 0,
        },
    }
    result_path = run / "result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")
    return tmp_path / "jobs", result_path


def test_resolved_config_separates_control_and_treatment(tmp_path: Path) -> None:
    treatment = json.loads(_resolved_treatment(tmp_path).read_text(encoding="utf-8"))
    assert resolved_config_failures(treatment, condition="treatment") == []

    control = deepcopy(treatment)
    control["agents"][0].pop("mcp_servers")
    control["environment"]["extra_docker_compose"] = [
        "benchmarks/config/agent-eval-proxy.compose.yaml"
    ]
    assert resolved_config_failures(control, condition="control") == []
    assert resolved_config_failures(treatment, condition="control")


def test_optional_correct_no_call_is_valid_routing_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(observation_results, "task_digest", lambda _path: "a" * 64)
    monkeypatch.setattr(observation_results, "_git_sha", lambda: "b" * 40)
    config = _resolved_treatment(tmp_path)
    jobs_dir, result = _routing_result(
        tmp_path,
        [{"type": "turn.completed", "usage": {"input_tokens": 10}}],
    )

    report, failures = build_routing_observation(
        dataset="agent-workflow-v1",
        condition="treatment",
        resolved_config_path=config,
        jobs_dir=jobs_dir,
        result_path=result,
    )

    assert failures == []
    assert report["status"] == "VALID"
    assert report["trials"][0]["routing_status"] == "AVAILABLE_NO_CALL"
    assert report["trials"][0]["opportunity"]["value"] == "OPTIONAL"
    assert report["summary"]["by_tool_opportunity"]["OPTIONAL"] == {
        "trials": 1,
        "used": 0,
        "adoption_rate": 0.0,
    }


def test_routing_observation_distinguishes_discovery_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(observation_results, "task_digest", lambda _path: "a" * 64)
    monkeypatch.setattr(observation_results, "_git_sha", lambda: "b" * 40)
    config = _resolved_treatment(tmp_path)
    describe = {
        "type": "item.completed",
        "item": {
            "type": "mcp_tool_call",
            "tool": "capability.describe",
            "arguments": {"query": "finite graph"},
            "status": "completed",
            "result": {
                "isError": False,
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "kind": "discovery",
                                "matches": [
                                    {"capability_id": "graph.compute.properties"}
                                ],
                            }
                        ),
                    }
                ],
            },
        },
    }
    jobs_dir, result = _routing_result(tmp_path, [describe])

    report, failures = build_routing_observation(
        dataset="agent-workflow-v1",
        condition="treatment",
        resolved_config_path=config,
        jobs_dir=jobs_dir,
        result_path=result,
    )

    assert failures == []
    assert report["trials"][0]["routing_status"] == "DISCOVERY_MISS"


@pytest.mark.parametrize(
    ("condition", "config_failures", "trace", "expected"),
    [
        ("control", [], {}, "NOT_CONFIGURED"),
        ("treatment", ["missing sidecar"], {}, "HARNESS_UNAVAILABLE"),
        ("treatment", [], {}, "EVIDENCE_INCOMPLETE"),
        (
            "treatment",
            [],
            {
                "raw_transcript_present": True,
                "telemetry_error": None,
                "telemetry": {
                    "mcp_calls": ["capability.describe"],
                    "capability_ids": [],
                    "capability_attempt_ids": [],
                    "capability_descriptions": [
                        {"capability_id": "graph.search.atlas", "match_ids": []}
                    ],
                },
            },
            "DESCRIBED_NOT_INVOKED",
        ),
        (
            "treatment",
            [],
            {
                "raw_transcript_present": True,
                "telemetry_error": None,
                "telemetry": {
                    "mcp_calls": ["capability.invoke"],
                    "capability_ids": [],
                    "capability_attempt_ids": ["graph.search.atlas"],
                    "capability_descriptions": [],
                },
            },
            "INVOKE_FAILED",
        ),
        (
            "treatment",
            [],
            {
                "raw_transcript_present": True,
                "telemetry_error": None,
                "telemetry": {
                    "mcp_calls": ["capability.invoke"],
                    "capability_ids": ["graph.search.atlas"],
                    "capability_attempt_ids": ["graph.search.atlas"],
                    "capability_descriptions": [],
                },
            },
            "USED",
        ),
    ],
)
def test_routing_status_classification(
    condition: str,
    config_failures: list[str],
    trace: dict,
    expected: str,
) -> None:
    opportunity = {
        "value": "HIGH",
        "relevant_capability_ids": ["graph.search.atlas"],
        "rationale": "bounded complete enumeration",
    }

    assert (
        observation_results._routing_status(
            condition=condition,
            config_failures=config_failures,
            trace=trace,
            opportunity=opportunity,
        )
        == expected
    )
