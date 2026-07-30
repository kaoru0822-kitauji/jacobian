from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[3]
DATASET = ROOT / "benchmarks" / "regression-v1"
TASKS = DATASET / "tasks"
EXPECTED_TASKS = {
    "graph-counterexample",
    "graph-artifact-composition",
    "finite-partition",
    "sat-witness",
    "rational-linear-solution",
    "hermite-normal-form",
    "polynomial-normalization",
    "polynomial-map-collision",
}


def test_regression_v1_is_a_frozen_eight_task_dataset() -> None:
    manifest = tomllib.loads((DATASET / "dataset.toml").read_text())
    assert manifest["dataset"]["name"] == "jacobian/regression-v1"
    assert {
        task["name"].rsplit("/", 1)[-1].removeprefix("regression-v1-")
        for task in manifest["tasks"]
    } == EXPECTED_TASKS

    task_dirs = {path.name for path in TASKS.iterdir() if path.is_dir()}
    assert task_dirs == EXPECTED_TASKS

    for task_name in sorted(EXPECTED_TASKS):
        task = TASKS / task_name
        spec = tomllib.loads((task / "task.toml").read_text())
        assert spec["schema_version"] == "1.4"
        assert spec["task"]["name"] == f"jacobian/regression-v1-{task_name}"
        assert spec["environment"]["network_mode"] == "no-network"
        assert spec["verifier"]["environment"]["network_mode"] == "no-network"

        input_bytes = (task / "input.json").read_bytes()
        assert input_bytes == (task / "environment" / "input.json").read_bytes()
        assert input_bytes == (task / "tests" / "input.json").read_bytes()
        json.loads(input_bytes)
        input_digest = "sha256:" + hashlib.sha256(input_bytes).hexdigest()
        metadata = json.loads((task / "metadata.json").read_text())
        assert metadata["case_version"] == "regression-v1"
        assert metadata["fixture_digest"] == input_digest
        assert (
            json.loads((task / "environment" / "metadata.json").read_text()) == metadata
        )
        assert spec["metadata"]["fixture_digest"] == input_digest
        assert metadata["upstream"] is None

        instruction = (task / "instruction.md").read_text()
        submission_schema = json.loads(
            (task / "environment" / "submission_schema.json").read_text()
        )
        assert submission_schema["type"] == "object"
        assert submission_schema["additionalProperties"] is False
        assert set(submission_schema["required"]) == {
            "task_id",
            "conclusion",
            "result",
            "claimed_assurance",
            "scope",
            "completeness",
            "evidence",
            "limitations",
        }
        assert "submission_schema.json" in instruction
        assert "evidence/answer.txt" in instruction
        assert "capability_id" not in instruction
        assert "agent-specific" not in instruction.lower()
        assert "jacobian" not in instruction.lower()
        assert "toolbox" not in instruction.lower()

        for dockerfile in (
            task / "environment" / "Dockerfile",
            task / "tests" / "Dockerfile",
        ):
            assert "@sha256:" in dockerfile.read_text()
        assert (
            "submission_schema.json"
            in (task / "environment" / "Dockerfile").read_text()
        )
