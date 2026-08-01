from __future__ import annotations

import json
import subprocess
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
    assert job["agents"] == [{"name": "codex"}]


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


def test_agent_eval_rejects_invalid_toggle_and_clears_control_mcp() -> None:
    invalid = subprocess.run(
        ["make", "-n", "agent-eval", "JACOBIAN_ENABLED=false"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert invalid.returncode != 0
    assert "JACOBIAN_ENABLED must be exactly 0 or 1" in invalid.stderr

    control = subprocess.run(
        [
            "make",
            "-n",
            "agent-eval",
            "JACOBIAN_ENABLED=0",
            "MCP_CONFIG=unexpected.json",
            "EVAL_EXECUTE=1",
            "JACOBIAN_MODEL=test",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--mcp-config" not in control.stdout
