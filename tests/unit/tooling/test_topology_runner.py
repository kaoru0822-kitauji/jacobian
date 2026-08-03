from __future__ import annotations

from pathlib import Path

from tools.test_topology import load_topology, main, pytest_command

ROOT = Path(__file__).resolve().parents[3]


def test_focused_selector_does_not_start_configured_workers() -> None:
    topology = load_topology(ROOT / "tests" / "topology.toml")

    command = pytest_command(
        topology,
        "process",
        ["tests/boundary/process/tooling/test_local_validation_tools.py::test_x"],
    )

    assert "-n" not in command
    assert "--dist" not in command
    assert (
        "tests/boundary/process/tooling/test_local_validation_tools.py::test_x"
        in command
    )


def test_full_parallel_lane_retains_configured_workers() -> None:
    topology = load_topology(ROOT / "tests" / "topology.toml")

    command = pytest_command(topology, "process")

    assert command[command.index("-n") + 1] == "2"
    assert command[command.index("--dist") + 1] == "worksteal"


def test_focused_serial_lane_remains_serial_and_preserves_extra_args() -> None:
    topology = load_topology(ROOT / "tests" / "topology.toml")

    command = pytest_command(
        topology,
        "lean",
        ["tests/boundary/providers/lean/test_lean_repl_runtime.py::test_x"],
        ["-k", "test_x"],
    )

    assert "-n" not in command
    assert command[command.index("-k") + 1] == "test_x"
    assert command[command.index("--timeout") + 1] == "300"


def test_dry_run_full_lane_reports_configured_metadata_and_command(capsys) -> None:
    rc = main(["composition", "--dry-run"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "# lane: composition" in out
    assert "# tier: composition" in out
    assert "# workers: 2" in out
    assert "# distribution: worksteal" in out
    assert "# timeout_seconds: 120" in out
    assert "# timing_sharding: true" in out
    assert "# selectors:" not in out
    # The command remains the final un-prefixed line and stays consumable.
    assert "tests/composition" in out
    assert "--timeout 120" in out


def test_dry_run_focused_selector_reports_zero_workers(capsys) -> None:
    rc = main(
        [
            "composition",
            "tests/composition/test_x.py::test_x",
            "--dry-run",
        ]
    )
    out = capsys.readouterr().out

    assert rc == 0
    assert "# workers: 0" in out
    assert "# distribution: none" in out
    assert "# selectors: 1" in out
    assert "-n" not in out.splitlines()[-1]


def test_dry_run_serial_lane_reports_no_workers(capsys) -> None:
    rc = main(["storage", "--dry-run"])
    out = capsys.readouterr().out

    assert rc == 0
    assert "# lane: storage" in out
    assert "# workers: 0" in out
    assert "# distribution: none" in out
    assert "# timing_sharding: false" in out
    assert "tests/boundary/storage" in out
