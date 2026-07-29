from __future__ import annotations

from pathlib import Path

from tools.test_topology import load_topology

ROOT = Path(__file__).resolve().parents[3]


def test_every_test_module_has_one_semantic_lane() -> None:
    topology = load_topology(ROOT / "tests" / "topology.toml")
    test_files = sorted((ROOT / "tests").rglob("test_*.py"))
    for path in test_files:
        relative = path.relative_to(ROOT).as_posix()
        owners = [
            lane.name
            for lane in topology.lanes
            if any(
                relative == owned or relative.startswith(owned.rstrip("/") + "/")
                for owned in lane.paths
            )
        ]
        assert len(owners) == 1, f"{relative} has lanes {owners}"


def test_obsolete_catch_all_directories_are_absent() -> None:
    for name in (
        "integration",
        "contract",
        "checkers",
        "reference",
        "end_to_end",
        "helpers",
        "fixtures",
    ):
        assert not (ROOT / "tests" / name).exists()
