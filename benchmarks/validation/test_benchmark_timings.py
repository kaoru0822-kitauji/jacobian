from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.tooling.benchmark_timings import collect, comparison_report
from benchmarks.tooling.errors import HarborSuiteError
from benchmarks.tooling.harbor_suite import get_suite


def test_timing_collector_uses_median_completed_trial_duration(tmp_path: Path) -> None:
    task = get_suite("mathematical-benchmarks-v1").tasks[0].path.name
    for index, minute in enumerate((1, 3, 2)):
        path = tmp_path / str(index) / "result.json"
        path.parent.mkdir()
        path.write_text(
            json.dumps(
                {
                    "task_name": f"jacobian/{task}",
                    "started_at": "2026-01-01T00:00:00Z",
                    "finished_at": f"2026-01-01T00:0{minute}:00Z",
                }
            ),
            encoding="utf-8",
        )

    timings = collect(tmp_path)

    assert timings[f"mathematical-benchmarks-v1/{task}"] == 120.0


def test_timing_collector_fails_closed_without_trials(tmp_path: Path) -> None:
    with pytest.raises(HarborSuiteError, match="no completed"):
        collect(tmp_path)


def test_timing_collector_includes_successful_pytest_receipt(tmp_path: Path) -> None:
    receipt = tmp_path / "host" / "pytest-receipt.json"
    receipt.parent.mkdir()
    receipt.write_text(
        json.dumps({"name": "full-1-of-4", "actual_seconds": 171.25, "exit_code": 0}),
        encoding="utf-8",
    )

    assert collect(tmp_path)["host-validation/full-1-of-4"] == 171.25


def test_timing_collector_reads_provenance_receipt_entry_name(tmp_path: Path) -> None:
    receipt = tmp_path / "host" / "pytest-receipt.json"
    receipt.parent.mkdir()
    receipt.write_text(
        json.dumps(
            {
                "entry": {"name": "full-2-of-4"},
                "actual_seconds": 173.0,
                "exit_code": 0,
            }
        ),
        encoding="utf-8",
    )

    assert collect(tmp_path)["host-validation/full-2-of-4"] == 173.0


def test_comparison_report_records_predicted_and_actual_shards() -> None:
    report = comparison_report(
        {
            "dataset/task-a": 10.0,
            "dataset/task-b": 15.0,
            "host-validation/full-1-of-4": 171.0,
        },
        oracle_matrix=[
            {
                "dataset": "dataset",
                "shard": "01-of-01",
                "tasks": ["task-a", "task-b"],
                "predicted_seconds": 20.0,
            }
        ],
        host_matrix=[{"name": "full-1-of-4", "predicted_seconds": 180.0}],
    )

    assert report["shards"] == [
        {
            "kind": "oracle",
            "name": "dataset/01-of-01",
            "predicted_seconds": 20.0,
            "actual_seconds": 25.0,
            "delta_seconds": 5.0,
            "actual_to_predicted": 1.25,
            "missing": [],
        },
        {
            "kind": "host",
            "name": "full-1-of-4",
            "predicted_seconds": 180.0,
            "actual_seconds": 171.0,
            "delta_seconds": -9.0,
            "actual_to_predicted": 0.95,
            "missing": [],
        },
    ]
