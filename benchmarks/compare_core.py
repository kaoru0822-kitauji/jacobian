"""Compare two pyperf runs of Jacobian's core benchmark suite."""

from __future__ import annotations

import argparse
from pathlib import Path

import pyperf

_SUITE = "jacobian-v0.2-core"


def _load(path: Path) -> dict[str, pyperf.Benchmark]:
    suite = pyperf.BenchmarkSuite.load(str(path))
    if suite.get_metadata().get("suite") != _SUITE:
        raise ValueError(f"{path} is not a {_SUITE} benchmark")
    return {benchmark.get_name(): benchmark for benchmark in suite}


def compare(
    baseline_path: Path,
    current_path: Path,
    *,
    threshold_percent: float = 20.0,
) -> str:
    """Return a Markdown comparison, classifying large changes as regressions."""

    if threshold_percent <= 0:
        raise ValueError("threshold_percent must be positive")
    baseline = _load(baseline_path)
    current = _load(current_path)
    if not baseline or not current:
        raise ValueError("benchmark suites must contain at least one benchmark")
    if baseline.keys() != current.keys():
        missing = ", ".join(sorted(baseline.keys() - current.keys())) or "none"
        added = ", ".join(sorted(current.keys() - baseline.keys())) or "none"
        raise ValueError(f"benchmark sets differ (missing: {missing}; added: {added})")

    rows: list[tuple[str, float, float, float, str]] = []
    for name in sorted(current):
        before = baseline[name].mean()
        after = current[name].mean()
        if before <= 0 or after <= 0:
            raise ValueError(f"benchmark {name!r} has a non-positive mean")
        change = (after / before - 1) * 100
        status = (
            "REGRESSION"
            if change >= threshold_percent
            else "IMPROVEMENT"
            if change <= -threshold_percent
            else "WITHIN NOISE"
        )
        rows.append((name, before, after, change, status))

    lines = [
        "## Core benchmark comparison",
        "",
        f"Report-only threshold: ±{threshold_percent:.1f}%.",
        "",
        "| Benchmark | Baseline | Current | Change | Classification |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for name, before, after, change, status in rows:
        lines.append(
            f"| `{name}` | {before:.3e}s | {after:.3e}s | {change:+.1f}% | {status} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold-percent", type=float, default=20.0)
    args = parser.parse_args()
    report = compare(
        args.baseline,
        args.current,
        threshold_percent=args.threshold_percent,
    )
    args.output.write_text(report, encoding="utf-8")
    print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
