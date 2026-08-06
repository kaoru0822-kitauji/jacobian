"""Stable fail-closed aggregate validation for the benchmark workflow."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from benchmarks.tooling.errors import HarborSuiteError
from benchmarks.tooling.host_validation import (
    load_plan_receipt,
    timing_digest,
    validate_receipts,
)


@dataclass(frozen=True, slots=True)
class LaneResult:
    """Planner selection and observed GitHub job result for one evidence lane."""

    selected: bool
    result: str


def _validate_lane(name: str, lane: LaneResult) -> None:
    expected = "success" if lane.selected else "skipped"
    if lane.result != expected:
        raise HarborSuiteError(
            f"benchmark lane {name} expected {expected}, observed {lane.result}"
        )


def validate_aggregate(
    *,
    plan_result: str,
    plan_receipt: Path,
    execution_sha: str,
    lanes: dict[str, LaneResult],
    receipt_root: Path | None,
    timing_path: Path | None,
) -> None:
    """Validate stable lane results and exact host-shard execution evidence."""

    if plan_result != "success":
        raise HarborSuiteError(f"benchmark planner did not succeed: {plan_result}")
    provenance, host_entries = load_plan_receipt(
        plan_receipt, execution_sha=execution_sha
    )
    receipt = json.loads(plan_receipt.read_text(encoding="utf-8"))
    plan = receipt["plan"]
    expected_flags = {
        "static": plan["run-benchmark-check"] == "true",
        "contracts": plan["run-benchmark-record-schema"] == "true",
        "host-validation": plan["run-benchmark-host-validation"] == "true",
        "inventory": plan["run-benchmark-inventory"] == "true",
        "oracle": plan["run-benchmark-oracle"] == "true",
    }
    if set(lanes) != set(expected_flags):
        raise HarborSuiteError("benchmark aggregate lane set is incomplete")
    for name, selected in expected_flags.items():
        lane = lanes[name]
        if lane.selected != selected:
            raise HarborSuiteError(
                f"benchmark aggregate selection disagrees for {name}"
            )
        _validate_lane(name, lane)
    if expected_flags["host-validation"]:
        if receipt_root is None or timing_path is None:
            raise HarborSuiteError("selected host validation has no receipt evidence")
        validate_receipts(
            receipt_root,
            expected=host_entries,
            provenance=provenance,
            timing_digest=timing_digest(timing_path),
        )
    elif host_entries:
        raise HarborSuiteError("unselected host validation has a non-empty matrix")


def _lane(value: str) -> tuple[str, LaneResult]:
    parts = value.split(":", 2)
    if len(parts) != 3 or parts[1] not in {"true", "false"}:
        raise argparse.ArgumentTypeError("lanes must use name:true|false:result")
    return parts[0], LaneResult(selected=parts[1] == "true", result=parts[2])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-result", required=True)
    parser.add_argument("--plan-receipt", type=Path, required=True)
    parser.add_argument("--execution-sha", required=True)
    parser.add_argument("--lane", action="append", type=_lane, required=True)
    parser.add_argument("--receipt-root", type=Path)
    parser.add_argument("--timings", type=Path)
    args = parser.parse_args(argv)
    try:
        lanes = dict(args.lane)
        if len(lanes) != len(args.lane):
            raise HarborSuiteError("benchmark aggregate lanes must be unique")
        validate_aggregate(
            plan_result=args.plan_result,
            plan_receipt=args.plan_receipt,
            execution_sha=args.execution_sha,
            lanes=lanes,
            receipt_root=args.receipt_root,
            timing_path=args.timings,
        )
    except (HarborSuiteError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["LaneResult", "validate_aggregate"]
