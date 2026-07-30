from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.compare_core import compare
from benchmarks.compare_startup import compare as compare_startup


def _write_suite(
    path: Path,
    benchmarks: dict[str, float],
    *,
    suite: str = "jacobian-v0.2-core",
) -> None:
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
                    "suite": suite,
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


def test_startup_comparison_applies_phase_specific_improvement_gates(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    phases = {
        "fresh-materialization": 10.0,
        "core-service-assembly": 4.0,
        "attachment": 2.0,
        "authorized-reference-hydration": 3.0,
        "store-bootstrap": 1.0,
    }
    _write_suite(baseline, phases, suite="jacobian-startup-phases")
    _write_suite(
        current,
        {
            "fresh-materialization": 6.5,
            "core-service-assembly": 2.0,
            "attachment": 0.8,
            "authorized-reference-hydration": 1.6,
            "store-bootstrap": 0.9,
        },
        suite="jacobian-startup-phases",
    )

    report, passed = compare_startup(baseline, current)

    assert not passed
    assert "`fresh-materialization`" in report
    assert "PASS (≥30%)" in report
    assert "`attachment`" in report
    assert "MISS (≥65%)" in report
    assert "`store-bootstrap`" in report
    assert "MEASURED" in report
