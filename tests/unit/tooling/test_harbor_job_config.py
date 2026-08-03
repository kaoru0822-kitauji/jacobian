from __future__ import annotations

import json
from pathlib import Path

from benchmarks.tooling.harbor_suite import get_suite

ROOT = Path(__file__).parents[3]
JOB = (
    ROOT
    / "benchmarks"
    / "datasets"
    / "agent-workflow-v1"
    / "jobs"
    / "jacobian-observation.json"
)
CONTROL_JOB = ROOT / "benchmarks" / "config" / "agent-workflow-v1-control.json"
MCP_CONFIG = ROOT / "benchmarks" / "config" / "jacobian.mcp.json"


def test_observation_job_uses_harbor_dataset_selection() -> None:
    job = json.loads(JOB.read_text())

    assert "tasks" not in job
    assert job["datasets"] == [
        {
            "path": "benchmarks/datasets/agent-workflow-v1",
            "task_names": ["graph-counterexample"],
        }
    ]
    assert job["agents"] == [{"name": "codex", "kwargs": {"web_search": "disabled"}}]
    assert job["environment"]["extra_allowed_hosts"] == [
        "api.openai.com",
        "auth.openai.com",
        "chatgpt.com",
        "deb.debian.org",
        "nodejs.org",
        "npmjs.org",
        "registry.npmjs.org",
        "raw.githubusercontent.com",
    ]


def test_observation_job_keeps_the_minimal_jacobian_treatment() -> None:
    job = json.loads(JOB.read_text())

    assert job["agents"] == [{"name": "codex", "kwargs": {"web_search": "disabled"}}]
    assert job["environment"]["extra_docker_compose"] == [
        "benchmarks/datasets/agent-workflow-v1/jacobian-observation.compose.yaml"
    ]


def test_agent_eval_forwards_web_search_setting_to_harbor() -> None:
    makefile = (ROOT / "Makefile").read_text()

    assert '--ak "web_search=$(CODEX_WEB_SEARCH)"' in makefile
    assert "JACOBIAN_EVAL_PROXY" in makefile
    assert (
        "JACOBIAN_EVAL_HTTP_PROXY ?= $(call _jacobian_eval_container_proxy,$(HTTP_PROXY))"
        in makefile
    )
    assert (
        "JACOBIAN_EVAL_HTTPS_PROXY ?= $(call _jacobian_eval_container_proxy,$(HTTPS_PROXY))"
        in makefile
    )
    assert (
        "JACOBIAN_EVAL_ALL_PROXY ?= $(call _jacobian_eval_container_proxy,$(ALL_PROXY))"
        in makefile
    )
    assert 'JACOBIAN_EVAL_NO_PROXY="$(JACOBIAN_EVAL_NO_PROXY)"' in makefile
    assert "agent-workflow-v1-control-proxy.json" in makefile
    assert "jacobian-observation-proxy.json" in makefile


def test_proxy_observation_job_is_opt_in_and_preserves_local_mcp_access() -> None:
    proxy_job = json.loads(
        (
            ROOT
            / "benchmarks"
            / "datasets"
            / "agent-workflow-v1"
            / "jobs"
            / "jacobian-observation-proxy.json"
        ).read_text()
    )
    proxy_overlay = (
        ROOT / "benchmarks" / "config" / "agent-eval-proxy.compose.yaml"
    ).read_text()

    assert proxy_job["environment"]["extra_docker_compose"] == [
        "benchmarks/config/agent-eval-proxy.compose.yaml",
        "benchmarks/datasets/agent-workflow-v1/jacobian-observation.compose.yaml",
    ]
    assert "NO_PROXY" in proxy_overlay
    assert "jacobian" in proxy_overlay


def test_observation_mcp_config_is_external_to_the_task_job() -> None:
    job = json.loads(JOB.read_text())
    control = json.loads(CONTROL_JOB.read_text())
    mcp = json.loads(MCP_CONFIG.read_text())

    assert "mcp_servers" not in job["agents"][0]
    assert "mcp_servers" not in control["agents"][0]
    assert mcp["mcp_servers"] == [
        {
            "name": "jacobian",
            "transport": "streamable-http",
            "url": "http://jacobian:8000/mcp",
        }
    ]


def test_observation_dataset_contains_the_canonical_task() -> None:
    suite = get_suite("agent-workflow-v1")

    assert any(ref.path.name == "graph-counterexample" for ref in suite.tasks)


def test_paired_jobs_use_three_attempts_per_condition() -> None:
    treatment = json.loads(JOB.read_text())
    control = json.loads(CONTROL_JOB.read_text())

    assert treatment["n_attempts"] == 3
    assert control["n_attempts"] == 3
