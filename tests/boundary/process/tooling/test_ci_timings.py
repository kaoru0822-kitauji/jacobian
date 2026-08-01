from __future__ import annotations

import json
from pathlib import Path

from tests.boundary.process.tooling.ci import run_ci_script


def test_ci_timing_summary_reports_elapsed_and_runner_minutes(tmp_path: Path) -> None:
    payload = {
        "jobs": [
            {
                "name": "Core",
                "started_at": "2026-07-27T10:00:00Z",
                "completed_at": "2026-07-27T10:02:00Z",
            },
            {
                "name": "Tests (domain 1 of 4, Python 3.12)",
                "started_at": "2026-07-27T10:01:00Z",
                "completed_at": "2026-07-27T10:05:00Z",
            },
            {
                "name": "Tests (domain 2 of 4, Python 3.12)",
                "started_at": "2026-07-27T10:01:00Z",
                "completed_at": "2026-07-27T10:03:00Z",
            },
            {
                "name": "Tests (domain 3 of 4, Python 3.12)",
                "started_at": "2026-07-27T10:01:00Z",
                "completed_at": "2026-07-27T10:03:30Z",
            },
            {
                "name": "Tests (domain 4 of 4, Python 3.12)",
                "started_at": "2026-07-27T10:01:00Z",
                "completed_at": "2026-07-27T10:03:00Z",
            },
            {
                "name": "CI Metrics",
                "started_at": "2026-07-27T10:05:00Z",
                "completed_at": "2026-07-27T10:06:00Z",
            },
            {
                "name": "Tests (composition 1 of 2, Python 3.12)",
                "started_at": "2026-07-27T10:00:00Z",
                "completed_at": "2026-07-27T10:03:00Z",
            },
            {
                "name": "Tests (composition 2 of 2, Python 3.12)",
                "started_at": "2026-07-27T10:00:00Z",
                "completed_at": "2026-07-27T10:02:00Z",
            },
        ]
    }
    jobs_json = tmp_path / "jobs.json"
    jobs_json.write_text(json.dumps(payload), encoding="utf-8")

    completed = run_ci_script("summarize-ci-timings", jobs_json, check=True)

    assert "Critical span | 5.0 min" in completed.stdout
    assert "Total runner time | 17.5 min" in completed.stdout
    assert "Tests (domain 1 of 4, Python 3.12) (4.0 min)" in completed.stdout
    assert "Domain shard skew (max/min) | 2.00x" in completed.stdout
    assert "Composition shard skew (max/min) | 1.50x" in completed.stdout
    assert "equal weighting" in completed.stdout
