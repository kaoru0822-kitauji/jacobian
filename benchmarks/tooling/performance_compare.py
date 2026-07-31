"""Report-only comparisons for raw performance task artifacts."""

from __future__ import annotations

from pathlib import Path

import pyperf


def _load(path: Path, expected_suite: str) -> dict[str, pyperf.Benchmark]:
    suite = pyperf.BenchmarkSuite.load(str(path))
    if suite.get_metadata().get("suite") != expected_suite:
        raise ValueError(f"{path} is not a {expected_suite} benchmark")
    return {benchmark.get_name(): benchmark for benchmark in suite}


def compare(
    baseline_path: Path, current_path: Path, *, threshold_percent: float = 20.0
) -> str:
    baseline = _load(baseline_path, "jacobian-v0.2-core")
    current = _load(current_path, "jacobian-v0.2-core")
    if not baseline or not current:
        raise ValueError("benchmark suites must contain at least one benchmark")
    if baseline.keys() != current.keys():
        raise ValueError("benchmark sets differ")
    lines = [
        "## Core benchmark comparison",
        "",
        f"Report-only threshold: ±{threshold_percent:.1f}%.",
        "",
        "| Benchmark | Baseline | Current | Change | Classification |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for name in sorted(current):
        before, after = baseline[name].mean(), current[name].mean()
        change = (after / before - 1) * 100
        status = (
            "REGRESSION"
            if change >= threshold_percent
            else "IMPROVEMENT"
            if change <= -threshold_percent
            else "WITHIN NOISE"
        )
        lines.append(
            f"| `{name}` | {before:.3e}s | {after:.3e}s | {change:+.1f}% | {status} |"
        )
    return "\n".join(lines) + "\n"


def compare_startup(baseline_path: Path, current_path: Path) -> tuple[str, bool]:
    baseline = _load(baseline_path, "jacobian-startup-phases")
    current = _load(current_path, "jacobian-startup-phases")
    if not baseline or not current or baseline.keys() != current.keys():
        raise ValueError("benchmark sets differ or are empty")
    gates = {
        "fresh-materialization": 30.0,
        "core-service-assembly": 50.0,
        "attachment": 65.0,
        "authorized-reference-hydration": 50.0,
    }
    if gates.keys() - current.keys():
        raise ValueError("startup benchmark is missing gated phases")
    passed = True
    lines = [
        "## Startup base-versus-head comparison",
        "",
        "Run both revisions on the same host with the same lock and pyperf options.",
        "",
        "| Phase | Base | Head | Improvement | Gate |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for name in sorted(current):
        before, after = baseline[name].mean(), current[name].mean()
        improvement = (1 - after / before) * 100
        target = gates.get(name)
        status = (
            "MEASURED"
            if target is None
            else f"PASS (≥{target:.0f}%)"
            if improvement >= target
            else f"MISS (≥{target:.0f}%)"
        )
        passed &= target is None or improvement >= target
        lines.append(
            f"| `{name}` | {before:.3e}s | {after:.3e}s | {improvement:+.1f}% | {status} |"
        )
    return "\n".join(lines) + "\n", passed
