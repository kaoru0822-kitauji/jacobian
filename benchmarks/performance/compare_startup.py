"""Compare same-host base and head runs of the startup phase benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path

import pyperf

_SUITE = "jacobian-startup-phases"
_IMPROVEMENT_GATES = {
    "fresh-materialization": 30.0,
    "core-service-assembly": 50.0,
    "attachment": 65.0,
    "authorized-reference-hydration": 50.0,
}


def _load(path: Path) -> dict[str, pyperf.Benchmark]:
    suite = pyperf.BenchmarkSuite.load(str(path))
    if suite.get_metadata().get("suite") != _SUITE:
        raise ValueError(f"{path} is not a {_SUITE} benchmark")
    return {benchmark.get_name(): benchmark for benchmark in suite}


def compare(baseline_path: Path, current_path: Path) -> tuple[str, bool]:
    """Return a Markdown base/head report and whether all startup gates passed."""

    baseline = _load(baseline_path)
    current = _load(current_path)
    if not baseline or not current:
        raise ValueError("benchmark suites must contain at least one benchmark")
    if baseline.keys() != current.keys():
        missing = ", ".join(sorted(baseline.keys() - current.keys())) or "none"
        added = ", ".join(sorted(current.keys() - baseline.keys())) or "none"
        raise ValueError(f"benchmark sets differ (missing: {missing}; added: {added})")
    absent_gates = sorted(_IMPROVEMENT_GATES.keys() - current.keys())
    if absent_gates:
        raise ValueError(f"startup benchmark is missing gated phases: {absent_gates}")

    rows: list[tuple[str, float, float, float, str]] = []
    passed = True
    for name in sorted(current):
        before = baseline[name].mean()
        after = current[name].mean()
        if before <= 0 or after <= 0:
            raise ValueError(f"benchmark {name!r} has a non-positive mean")
        improvement = (1 - after / before) * 100
        target = _IMPROVEMENT_GATES.get(name)
        if target is None:
            status = "MEASURED"
        elif improvement >= target:
            status = f"PASS (≥{target:.0f}%)"
        else:
            status = f"MISS (≥{target:.0f}%)"
            passed = False
        rows.append((name, before, after, improvement, status))

    lines = [
        "## Startup base-versus-head comparison",
        "",
        "Run both revisions on the same host with the same lock and pyperf options.",
        "",
        "| Phase | Base | Head | Improvement | Gate |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for name, before, after, improvement, status in rows:
        lines.append(
            f"| `{name}` | {before:.3e}s | {after:.3e}s | "
            f"{improvement:+.1f}% | {status} |"
        )
    return "\n".join(lines) + "\n", passed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report, passed = compare(args.baseline, args.current)
    if args.output is not None:
        args.output.write_text(report, encoding="utf-8")
    print(report, end="")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
