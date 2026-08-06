"""Collect benchmark timings and compare planned with observed shard cost."""

from __future__ import annotations

import argparse
import json
import statistics
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from benchmarks.tooling.errors import HarborSuiteError
from benchmarks.tooling.harbor_suite import load_registry


def _seconds(started: Any, finished: Any) -> float | None:
    if not isinstance(started, str) or not isinstance(finished, str):
        return None
    try:
        start = datetime.fromisoformat(started.replace("Z", "+00:00"))
        finish = datetime.fromisoformat(finished.replace("Z", "+00:00"))
    except ValueError:
        return None
    value = (finish - start).total_seconds()
    return value if value > 0 else None


def collect(root: Path) -> dict[str, float]:
    samples: dict[str, list[float]] = {}
    _collect_oracle_timings(root, samples)
    _collect_host_timings(root, samples)
    if not samples:
        raise HarborSuiteError(f"no completed Harbor trial timings found below {root}")
    return {
        key: round(statistics.median(values), 6)
        for key, values in sorted(samples.items())
    }


def _collect_oracle_timings(root: Path, samples: dict[str, list[float]]) -> None:
    owners = {
        ref.path.name: suite.id for suite in load_registry() for ref in suite.tasks
    }
    for path in sorted(root.rglob("result.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or "task_name" not in payload:
            continue
        task = str(payload["task_name"]).rsplit("/", 1)[-1]
        dataset = owners.get(task)
        elapsed = _seconds(payload.get("started_at"), payload.get("finished_at"))
        if dataset is None or elapsed is None:
            continue
        samples.setdefault(f"{dataset}/{task}", []).append(elapsed)


def _collect_host_timings(root: Path, samples: dict[str, list[float]]) -> None:
    for path in sorted(root.rglob("pytest-receipt.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or payload.get("exit_code") != 0:
            continue
        entry = payload.get("entry")
        name = payload.get("name")
        if name is None and isinstance(entry, dict):
            name = entry.get("name")
        elapsed = payload.get("actual_seconds")
        if (
            not isinstance(name, str)
            or not name
            or not isinstance(elapsed, (int, float))
            or isinstance(elapsed, bool)
            or elapsed <= 0
        ):
            continue
        key = name if name.startswith("host-validation/") else f"host-validation/{name}"
        samples.setdefault(key, []).append(float(elapsed))


def _load_matrix(value: str | None) -> list[dict[str, Any]]:
    if not value:
        return []
    try:
        matrix = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HarborSuiteError(f"invalid timing matrix JSON: {exc}") from exc
    if not isinstance(matrix, list) or not all(
        isinstance(item, dict) for item in matrix
    ):
        raise HarborSuiteError("timing matrix must be an array of objects")
    return matrix


def comparison_report(
    timings: dict[str, float],
    *,
    oracle_matrix: Iterable[dict[str, Any]] = (),
    host_matrix: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Bind planner predictions to the durations observed for each matrix job."""
    shards: list[dict[str, Any]] = []
    for entry in oracle_matrix:
        dataset = entry.get("dataset")
        shard = entry.get("shard")
        tasks = entry.get("tasks")
        predicted = entry.get("predicted_seconds")
        if (
            not isinstance(dataset, str)
            or not isinstance(shard, str)
            or not isinstance(tasks, list)
        ):
            raise HarborSuiteError("Oracle timing matrix entry is malformed")
        observed = [timings.get(f"{dataset}/{task}") for task in tasks]
        oracle_actual = sum(value for value in observed if value is not None)
        missing = [
            task for task, value in zip(tasks, observed, strict=True) if value is None
        ]
        shards.append(
            _comparison_entry(
                kind="oracle",
                name=f"{dataset}/{shard}",
                predicted=predicted,
                actual=oracle_actual if not missing else None,
                missing=missing,
            )
        )
    for entry in host_matrix:
        name = entry.get("name")
        if not isinstance(name, str):
            raise HarborSuiteError("host timing matrix entry is malformed")
        host_actual = timings.get(f"host-validation/{name}")
        shards.append(
            _comparison_entry(
                kind="host",
                name=name,
                predicted=entry.get("predicted_seconds"),
                actual=host_actual,
                missing=[] if host_actual is not None else [name],
            )
        )
    return {"schema_version": 1, "shards": shards}


def _comparison_entry(
    *, kind: str, name: str, predicted: Any, actual: float | None, missing: list[str]
) -> dict[str, Any]:
    if (
        not isinstance(predicted, (int, float))
        or isinstance(predicted, bool)
        or predicted <= 0
    ):
        raise HarborSuiteError(f"timing prediction for {name} must be positive")
    predicted_value = round(float(predicted), 6)
    actual_value = round(actual, 6) if actual is not None else None
    return {
        "kind": kind,
        "name": name,
        "predicted_seconds": predicted_value,
        "actual_seconds": actual_value,
        "delta_seconds": (
            round(actual_value - predicted_value, 6)
            if actual_value is not None
            else None
        ),
        "actual_to_predicted": (
            round(actual_value / predicted_value, 6)
            if actual_value is not None
            else None
        ),
        "missing": missing,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "## Benchmark shard timing",
        "",
        "| Kind | Shard | Predicted | Actual | Ratio |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for shard in report["shards"]:
        actual = shard["actual_seconds"]
        ratio = shard["actual_to_predicted"]
        lines.append(
            f"| {shard['kind']} | `{shard['name']}` | "
            f"{shard['predicted_seconds']:.1f}s | "
            f"{actual:.1f}s | {ratio:.2f}x |"
            if actual is not None
            else f"| {shard['kind']} | `{shard['name']}` | "
            f"{shard['predicted_seconds']:.1f}s | unavailable | unavailable |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--oracle-matrix-json")
    parser.add_argument("--host-matrix-json")
    parser.add_argument("--report-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()
    try:
        timings = collect(args.root)
        if args.previous is not None and args.previous.is_file():
            previous = json.loads(args.previous.read_text(encoding="utf-8"))
            if not isinstance(previous, dict):
                raise HarborSuiteError("previous timing history must be an object")
            timings = {**previous, **timings}
        report = comparison_report(
            timings,
            oracle_matrix=_load_matrix(args.oracle_matrix_json),
            host_matrix=_load_matrix(args.host_matrix_json),
        )
    except HarborSuiteError as exc:
        parser.error(str(exc))
    args.output.write_text(
        json.dumps(timings, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.report_output is not None:
        args.report_output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if args.summary_output is not None:
        with args.summary_output.open("a", encoding="utf-8") as stream:
            stream.write(_markdown(report))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["collect", "comparison_report"]
