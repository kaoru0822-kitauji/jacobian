#!/usr/bin/env python3
"""Summarize retained pytest JUnit and optional worker timing evidence."""

from __future__ import annotations

import argparse
import json
import math
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO


@dataclass(frozen=True, slots=True)
class TestDuration:
    node_id: str
    seconds: float


@dataclass(frozen=True, slots=True)
class WorkerTiming:
    worker_id: str
    call_seconds: float
    call_count: int


@dataclass(frozen=True, slots=True)
class TimingSummary:
    test_count: int
    testcase_seconds: float
    slowest: tuple[TestDuration, ...]
    wall_seconds: float | None
    workers: tuple[WorkerTiming, ...]


def _nonnegative_float(value: Any, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{label} must be finite and nonnegative")
    return result


def read_junit(
    path: Path, *, limit: int
) -> tuple[int, float, tuple[TestDuration, ...]]:
    """Read testcase totals from a pytest JUnit XML artifact."""

    root = ET.parse(path).getroot()
    durations: list[TestDuration] = []
    for case in root.iter("testcase"):
        classname = case.get("classname", "")
        name = case.get("name", "")
        node_id = "::".join(part for part in (classname, name) if part)
        durations.append(
            TestDuration(
                node_id=node_id or "<unnamed testcase>",
                seconds=_nonnegative_float(
                    case.get("time", "0"), label="testcase time"
                ),
            )
        )
    ordered = tuple(sorted(durations, key=lambda item: (-item.seconds, item.node_id)))
    return len(ordered), sum(item.seconds for item in ordered), ordered[:limit]


def read_worker_timing(path: Path) -> tuple[float, tuple[WorkerTiming, ...]]:
    """Read one timing sidecar emitted by :mod:`tools.pytest_timing`."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("version") != 1:
        raise ValueError("timing evidence must be a version-1 object")
    wall_seconds = _nonnegative_float(raw.get("wall_seconds"), label="wall_seconds")
    raw_workers = raw.get("workers")
    if not isinstance(raw_workers, list) or not raw_workers:
        raise ValueError("timing evidence requires at least one worker")
    workers: list[WorkerTiming] = []
    for raw_worker in raw_workers:
        if not isinstance(raw_worker, dict):
            raise ValueError("worker timing must be an object")
        worker_id = raw_worker.get("id")
        call_count = raw_worker.get("call_count")
        if not isinstance(worker_id, str) or not worker_id:
            raise ValueError("worker id must be a nonempty string")
        if not isinstance(call_count, int) or call_count < 0:
            raise ValueError("worker call_count must be a nonnegative integer")
        workers.append(
            WorkerTiming(
                worker_id=worker_id,
                call_seconds=_nonnegative_float(
                    raw_worker.get("call_seconds"), label="worker call_seconds"
                ),
                call_count=call_count,
            )
        )
    return wall_seconds, tuple(sorted(workers, key=lambda worker: worker.worker_id))


def build_summary(*, junit: Path, timing: Path | None, limit: int) -> TimingSummary:
    test_count, testcase_seconds, slowest = read_junit(junit, limit=limit)
    if timing is None:
        return TimingSummary(test_count, testcase_seconds, slowest, None, ())
    wall_seconds, workers = read_worker_timing(timing)
    return TimingSummary(test_count, testcase_seconds, slowest, wall_seconds, workers)


def write_summary(summary: TimingSummary, *, stream: TextIO) -> None:
    """Write a compact human-readable timing report."""

    print(f"Testcases: {summary.test_count}", file=stream)
    print(f"JUnit testcase total: {summary.testcase_seconds:.3f}s", file=stream)
    print("Slowest testcases:", file=stream)
    for duration in summary.slowest:
        print(f"  {duration.seconds:8.3f}s  {duration.node_id}", file=stream)
    if summary.wall_seconds is None:
        print(
            "Worker timing: unavailable (pass --timing from the CI timing artifact).",
            file=stream,
        )
        return
    print(f"Invocation wall time: {summary.wall_seconds:.3f}s", file=stream)
    busiest = max(summary.workers, key=lambda worker: worker.call_seconds)
    positive = [
        worker.call_seconds for worker in summary.workers if worker.call_seconds
    ]
    skew_text = ""
    if len(positive) > 1:
        skew_text = f"; call-time skew {max(positive) / min(positive):.2f}x"
    print(f"Worker call-time distribution{skew_text}:", file=stream)
    for worker in summary.workers:
        print(
            f"  {worker.worker_id}: {worker.call_seconds:.3f}s across "
            f"{worker.call_count} tests",
            file=stream,
        )
    print(
        "Non-call wall remainder: "
        f"{max(0.0, summary.wall_seconds - busiest.call_seconds):.3f}s "
        "(collection, setup/teardown, scheduling, and process overhead).",
        file=stream,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--timing", type=Path)
    parser.add_argument("--limit", type=int, default=20)
    arguments = parser.parse_args(argv)
    if arguments.limit <= 0:
        parser.error("--limit must be positive")
    try:
        summary = build_summary(
            junit=arguments.junit, timing=arguments.timing, limit=arguments.limit
        )
    except (OSError, ValueError, ET.ParseError) as exc:
        parser.error(str(exc))
    write_summary(summary, stream=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
