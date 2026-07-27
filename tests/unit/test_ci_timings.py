from __future__ import annotations

import json
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / ".github" / "scripts" / "summarize-ci-timings"


def test_ci_timing_summary_reports_elapsed_and_runner_minutes(tmp_path: Path) -> None:
    payload = {
        "jobs": [
            {
                "name": "Core",
                "started_at": "2026-07-27T10:00:00Z",
                "completed_at": "2026-07-27T10:02:00Z",
            },
            {
                "name": "Tests (integration 1 of 3, Python 3.12)",
                "started_at": "2026-07-27T10:01:00Z",
                "completed_at": "2026-07-27T10:05:00Z",
            },
            {
                "name": "Tests (integration 2 of 3, Python 3.12)",
                "started_at": "2026-07-27T10:01:00Z",
                "completed_at": "2026-07-27T10:03:00Z",
            },
            {
                "name": "Tests (integration 3 of 3, Python 3.12)",
                "started_at": "2026-07-27T10:01:00Z",
                "completed_at": "2026-07-27T10:03:30Z",
            },
            {
                "name": "CI Metrics",
                "started_at": "2026-07-27T10:05:00Z",
                "completed_at": "2026-07-27T10:06:00Z",
            },
        ]
    }
    jobs_json = tmp_path / "jobs.json"
    jobs_json.write_text(json.dumps(payload), encoding="utf-8")

    completed = subprocess.run(
        [SCRIPT, jobs_json],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Critical path (workflow elapsed) | 5.0 min" in completed.stdout
    assert "Total runner time | 10.5 min" in completed.stdout
    assert "Tests (integration 1 of 3, Python 3.12) (4.0 min)" in completed.stdout
    assert "Integration shard skew (max/min) | 2.00x" in completed.stdout
    assert "make test-durations" in completed.stdout
