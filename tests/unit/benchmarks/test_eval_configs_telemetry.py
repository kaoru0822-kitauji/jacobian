from __future__ import annotations

from pathlib import Path

from benchmarks.jacobian_math_evals.configs import (
    condition_normalized,
    experiment_fingerprint,
    experiment_manifest,
    matched_configs,
    validate_treatment_environment,
    write_matched_configs,
)
from benchmarks.jacobian_math_evals.telemetry import summarize_events


def test_matched_configs_differ_only_on_jacobian_surface() -> None:
    control, treatment = matched_configs(dataset_path="generated/coverage")
    assert condition_normalized(control) == condition_normalized(treatment)
    assert experiment_fingerprint(control) == experiment_fingerprint(treatment)
    assert all("mcp_servers" not in agent for agent in control["agents"])
    assert all(
        agent["mcp_servers"][0]["name"] == "jacobian" for agent in treatment["agents"]
    )
    assert control["datasets"] == treatment["datasets"]


def test_experiment_manifest_randomizes_pair_order_deterministically() -> None:
    assert experiment_manifest(seed=1729)["condition_order"] == [
        "control",
        "treatment",
    ]
    assert experiment_manifest(seed=1731)["condition_order"] == [
        "treatment",
        "control",
    ]


def test_matched_config_files_are_deterministic(tmp_path: Path) -> None:
    first = write_matched_configs(tmp_path / "one", dataset_path="generated/coverage")
    second = write_matched_configs(tmp_path / "two", dataset_path="generated/coverage")
    assert [path.read_bytes() for path in first] == [
        path.read_bytes() for path in second
    ]


def test_process_summary_uses_only_observable_events() -> None:
    events = [
        {
            "kind": "capability.invoke",
            "capability_id": "algebra.factor",
            "arguments_digest": "sha256:a",
        },
        {
            "kind": "capability.invoke",
            "capability_id": "algebra.factor",
            "arguments_digest": "sha256:a",
        },
        {"kind": "capability.parameter_error"},
        {"kind": "artifact.produced", "artifact_uri": "artifact://one"},
        {"kind": "verification.record", "artifact_uri": "artifact://one"},
        {"kind": "hidden_chain_of_thought", "text": "must be ignored"},
    ]
    summary = summarize_events(
        events,
        outcome={
            "elapsed_seconds": 4.5,
            "input_tokens": 10,
            "output_tokens": 20,
            "cost_usd": 0.01,
            "completion_state": "COMPLETED",
            "false_certification": True,
        },
    )
    assert summary.repeated_invocations == 1
    assert summary.parameter_errors == 1
    assert summary.artifact_handoffs == 1
    assert "hidden_chain_of_thought" not in summary.event_counts
    assert summary.false_certification is True


def test_process_summary_does_not_conflate_unidentified_invocations() -> None:
    summary = summarize_events(
        [
            {"kind": "capability.invoke"},
            {"kind": "capability.invoke", "capability_id": "algebra.factor"},
        ],
        outcome={},
    )
    assert summary.event_counts["capability.invoke"] == 2
    assert summary.repeated_invocations == 0


def test_treatment_preflight_requires_pinned_image_and_matching_token() -> None:
    validate_treatment_environment(
        {
            "JACOBIAN_IMAGE": "registry/jacobian@sha256:" + "a" * 64,
            "JACOBIAN_MCP_TOKEN": "opaque",
            "JACOBIAN_AUTH_TOKENS_JSON": '{"opaque":"trial-1"}',
        }
    )
