from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.compare_core import compare


def _write_suite(path: Path, benchmarks: dict[str, float]) -> None:
    path.write_text(
        json.dumps(
            {
                "benchmarks": [
                    {
                        "runs": [
                            {
                                "metadata": {"name": name, "unit": "second"},
                                "values": [mean, mean],
                            }
                        ]
                    }
                    for name, mean in benchmarks.items()
                ],
                "metadata": {
                    "suite": "jacobian-v0.2-core",
                    "unit": "second",
                },
                "version": "1.0",
            }
        ),
        encoding="utf-8",
    )


def test_compare_classifies_large_changes(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_suite(baseline, {"artifact-read": 1.0})
    _write_suite(current, {"artifact-read": 1.25})

    report = compare(baseline, current)

    assert "REGRESSION" in report
    assert "+25.0%" in report


def test_compare_rejects_mismatched_benchmark_sets(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_suite(baseline, {"artifact-read": 1.0})
    _write_suite(current, {"artifact-write": 1.0})

    with pytest.raises(ValueError, match="benchmark sets differ"):
        compare(baseline, current)
