from __future__ import annotations

from pathlib import Path

import pytest
from tools.test_topology import (
    TopologyError,
    load_topology,
    pytest_command,
    validate_topology,
)

ROOT = Path(__file__).resolve().parents[3]


def test_manifest_assigns_each_test_file_once() -> None:
    topology = load_topology(ROOT / "tests" / "topology.toml")

    assert {lane.name for lane in topology.lanes} == {
        "unit",
        "component",
        "domain",
        "composition",
        "storage",
        "process",
        "mcp",
        "provider",
        "lean",
        "e2e",
    }
    assert all(lane.paths for lane in topology.lanes)
    assert all(lane.timeout_seconds > 0 for lane in topology.lanes)


def test_runner_preserves_exact_node_selector() -> None:
    topology = load_topology(ROOT / "tests" / "topology.toml")

    command = pytest_command(
        topology,
        "unit",
        ["tests/unit/test_arithmetic_base_digits.py::test_base_digits"],
    )

    assert command[:3] == [command[0], "-m", "pytest"]
    assert command[3] == "tests/unit/test_arithmetic_base_digits.py::test_base_digits"
    assert "tests/unit/contracts" not in command
    assert "--timeout" in command


def test_invalid_manifest_rejects_overlapping_ownership() -> None:
    data = {
        "version": 1,
        "lanes": [
            {
                "name": "one",
                "tier": "unit",
                "paths": ["tests/unit"],
                "workers": 0,
                "distribution": "none",
                "timeout_seconds": 10,
                "required_environment": [],
                "required_provider": "",
                "timing_sharding": False,
                "ci": {
                    "pull_request": True,
                    "merge_queue": True,
                    "main": True,
                    "scheduled": True,
                },
            },
            {
                "name": "two",
                "tier": "component",
                "paths": ["tests/unit"],
                "workers": 0,
                "distribution": "none",
                "timeout_seconds": 10,
                "required_environment": [],
                "required_provider": "",
                "timing_sharding": False,
                "ci": {
                    "pull_request": True,
                    "merge_queue": True,
                    "main": True,
                    "scheduled": True,
                },
            },
        ],
    }

    with pytest.raises(TopologyError, match="multiple lanes"):
        validate_topology(data, root=ROOT, manifest=ROOT / "tests" / "topology.toml")
