from __future__ import annotations

from pathlib import Path

from benchmarks.tooling.harbor_suite import ROOT
from benchmarks.tooling.observation_routing import (
    JACOBIAN_SERVER,
    _config_jobs_dir,
    _matches_opportunity,
    _routing_status,
    resolved_config_failures,
)


def test_routing_requires_an_explicit_relevant_capability() -> None:
    assert not _matches_opportunity({"graph.search.atlas"}, set())
    assert _matches_opportunity({"graph.search.atlas"}, {"graph.search.atlas"})


def test_unclassified_task_does_not_turn_another_capability_into_relevant_use() -> None:
    telemetry = {
        "transcript": {"path": "trial/agent/codex.txt", "digest": "sha256:" + "0" * 64},
        "turn_usage_present": True,
        "mcp_calls": ["capability.invoke"],
        "successful_mcp_calls": ["capability.invoke"],
        "tool_error_count": 0,
        "capability_attempt_ids": ["graph.search.atlas"],
        "capability_ids": ["graph.search.atlas"],
        "capability_descriptions": [],
    }
    assert (
        _routing_status(
            condition="treatment",
            config_failures=[],
            telemetry=telemetry,
            opportunity={"value": "UNASSESSED", "relevant_capability_ids": []},
        )
        == "USED_OTHER_CAPABILITY"
    )


def test_resolved_config_requires_exact_treatment_wiring() -> None:
    config = {
        "agents": [{"name": "codex", "mcp_servers": [JACOBIAN_SERVER]}],
        "environment": {
            "extra_docker_compose": [
                "benchmarks/datasets/agent-workflow-v1/jacobian-observation.compose.yaml"
            ]
        },
    }
    assert resolved_config_failures(config, condition="treatment") == []
    assert resolved_config_failures(
        {**config, "agents": [{"name": "codex", "mcp_servers": []}]},
        condition="treatment",
    )


def test_routing_uses_the_jobs_dir_bound_by_resolved_config() -> None:
    assert (
        _config_jobs_dir({"jobs_dir": "benchmarks/results/example"})
        == (ROOT / "benchmarks/results/example").resolve()
    )
    absolute = Path("/tmp/jacobian-results")
    assert _config_jobs_dir({"jobs_dir": str(absolute)}) == absolute
