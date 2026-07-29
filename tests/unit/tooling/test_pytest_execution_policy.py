from __future__ import annotations

from pathlib import Path

from tools.test_topology import load_topology, pytest_command

ROOT = Path(__file__).parents[3]


def test_lean_lane_is_serial_and_has_its_own_deadline() -> None:
    topology = load_topology(ROOT / "tests" / "topology.toml")

    command = pytest_command(topology, "lean")

    assert "-n" not in command
    assert command[command.index("--timeout") + 1] == "300"


def test_process_lane_uses_bounded_parallelism() -> None:
    topology = load_topology(ROOT / "tests" / "topology.toml")

    command = pytest_command(topology, "process")

    assert command[command.index("-n") + 1] == "2"
    assert command[command.index("--timeout") + 1] == "120"
