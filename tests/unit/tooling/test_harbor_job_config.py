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


def test_observation_job_uses_harbor_dataset_selection() -> None:
    job = json.loads(JOB.read_text())

    assert "tasks" not in job
    assert job["datasets"] == [
        {
            "path": "benchmarks/datasets/agent-workflow-v1",
            "task_names": ["graph-counterexample"],
        }
    ]
    assert job["agents"][0]["mcp_servers"][0]["url"] == ("http://jacobian:8000/mcp")


def test_observation_dataset_contains_the_canonical_task() -> None:
    suite = get_suite("agent-workflow-v1")

    assert any(ref.path.name == "graph-counterexample" for ref in suite.tasks)
