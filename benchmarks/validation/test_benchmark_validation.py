"""Fail-closed tests for the stable benchmark result aggregator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from benchmarks.tooling.benchmark_validation import LaneResult, validate_aggregate
from benchmarks.tooling.errors import HarborSuiteError
from benchmarks.tooling.host_validation import (
    ExecutionProvenance,
    ShardResult,
    build_receipt,
    load_plan_receipt,
)
from benchmarks.tooling.receipts import digest_bytes, receipt_digest
from benchmarks.tooling.validation_plan import full_host_validation
from tests.boundary.process.tooling.ci import run_ci_script

DIGEST = "sha256:" + "a" * 64
SHA = "1" * 40
EXECUTION_SHA = "2" * 40


def _digest(value: object) -> str:
    return receipt_digest(value)


def _plan_digest(plan: dict[str, str]) -> str:
    payload = "".join(f"{key}={plan[key]}\n" for key in sorted(plan)).encode()
    return digest_bytes(payload)


def _plan_receipt(tmp_path: Path) -> tuple[Path, ExecutionProvenance]:
    entries = full_host_validation()
    plan = {
        "benchmark-plan-head-sha": SHA,
        "benchmark-planner-digest": DIGEST,
        "benchmark-topology-digest": DIGEST,
        "benchmark-host-validation-matrix": json.dumps(
            [entry.as_matrix_entry() for entry in entries]
        ),
        "run-benchmark-check": "true",
        "run-benchmark-record-schema": "true",
        "run-benchmark-host-validation": "true",
        "run-benchmark-inventory": "false",
        "run-benchmark-oracle": "false",
    }
    receipt = {
        "receipt_version": "1",
        "plan_kind": "benchmark",
        "head_sha": SHA,
        "plan_digest": _plan_digest(plan),
        "plan": plan,
    }
    receipt["receipt_digest"] = _digest(receipt)
    path = tmp_path / "plan-receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    provenance = ExecutionProvenance(
        plan_head_sha=SHA,
        execution_sha=EXECUTION_SHA,
        planner_digest=DIGEST,
        topology_digest=DIGEST,
        plan_digest=receipt["plan_digest"],
        plan_receipt_digest=receipt["receipt_digest"],
    )
    return path, provenance


def _evidence(tmp_path: Path) -> tuple[Path, Path, Path]:
    plan_path, provenance = _plan_receipt(tmp_path)
    timings = tmp_path / "benchmark-test-durations.json"
    timings.write_text("{}\n", encoding="utf-8")
    timing_digest = digest_bytes(b"{}\n")
    receipt_root = tmp_path / "receipts"
    for entry in full_host_validation():
        payload = build_receipt(
            entry=entry,
            result=ShardResult(status="EXITED", exit_code=0, actual_seconds=3.0),
            provenance=provenance,
            timing_digest=timing_digest,
            workers=2,
            total_worker_budget=8,
            max_parallel=4,
            store_durations=True,
        )
        path = receipt_root / entry.name / "pytest-receipt.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    return plan_path, receipt_root, timings


def _lanes() -> dict[str, LaneResult]:
    return {
        "static": LaneResult(True, "success"),
        "contracts": LaneResult(True, "success"),
        "host-validation": LaneResult(True, "success"),
        "inventory": LaneResult(False, "skipped"),
        "oracle": LaneResult(False, "skipped"),
    }


def test_aggregate_accepts_exact_successful_shard_receipts(tmp_path: Path) -> None:
    plan, receipts, timings = _evidence(tmp_path)

    validate_aggregate(
        plan_result="success",
        plan_receipt=plan,
        execution_sha=EXECUTION_SHA,
        lanes=_lanes(),
        receipt_root=receipts,
        timing_path=timings,
    )


def test_real_plan_receipt_round_trips_through_consumer(tmp_path: Path) -> None:
    entries = full_host_validation()
    plan = {
        "benchmark-plan-head-sha": SHA,
        "benchmark-planner-digest": DIGEST,
        "benchmark-topology-digest": DIGEST,
        "benchmark-host-validation-matrix": json.dumps(
            [entry.as_matrix_entry() for entry in entries]
        ),
        "run-benchmark-check": "true",
        "run-benchmark-record-schema": "true",
        "run-benchmark-host-validation": "true",
        "run-benchmark-inventory": "false",
        "run-benchmark-oracle": "false",
    }
    plan_file = tmp_path / "plan.txt"
    plan_file.write_text(
        "".join(f"{key}={plan[key]}\n" for key in sorted(plan)), encoding="utf-8"
    )
    paths_file = tmp_path / "paths.txt"
    paths_file.write_text("README.md\n", encoding="utf-8")
    output = tmp_path / "receipt.json"

    run_ci_script(
        "emit-plan-receipt",
        "--kind",
        "benchmark",
        "--event",
        "pull_request",
        "--head",
        SHA,
        "--planner",
        ".github/scripts/plan-benchmarks",
        "--plan-file",
        plan_file,
        "--paths-file",
        paths_file,
        "--output",
        output,
        check=True,
    )

    provenance, observed = load_plan_receipt(output, execution_sha=EXECUTION_SHA)
    assert observed == entries
    assert provenance.plan_head_sha == SHA


def test_aggregate_accepts_consistent_empty_plan(tmp_path: Path) -> None:
    plan = {
        "benchmark-plan-head-sha": SHA,
        "benchmark-planner-digest": DIGEST,
        "benchmark-topology-digest": "",
        "benchmark-host-validation-matrix": "[]",
        "run-benchmark-check": "false",
        "run-benchmark-record-schema": "false",
        "run-benchmark-host-validation": "false",
        "run-benchmark-inventory": "false",
        "run-benchmark-oracle": "false",
    }
    receipt = {
        "receipt_version": "1",
        "plan_kind": "benchmark",
        "head_sha": SHA,
        "plan_digest": _plan_digest(plan),
        "plan": plan,
    }
    receipt["receipt_digest"] = receipt_digest(receipt)
    path = tmp_path / "plan-receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    lanes = {name: LaneResult(False, "skipped") for name in _lanes()}

    validate_aggregate(
        plan_result="success",
        plan_receipt=path,
        execution_sha=EXECUTION_SHA,
        lanes=lanes,
        receipt_root=None,
        timing_path=None,
    )


@pytest.mark.parametrize("failure", ["missing", "stale", "failed"])
def test_aggregate_rejects_invalid_host_evidence(tmp_path: Path, failure: str) -> None:
    plan, receipts, timings = _evidence(tmp_path)
    first = next(receipts.rglob("pytest-receipt.json"))
    if failure == "missing":
        first.unlink()
    else:
        payload = json.loads(first.read_text(encoding="utf-8"))
        if failure == "stale":
            payload["execution_sha"] = "3" * 40
        else:
            payload["exit_code"] = 1
        unsigned = {
            key: value for key, value in payload.items() if key != "receipt_digest"
        }
        payload["receipt_digest"] = _digest(unsigned)
        first.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(HarborSuiteError):
        validate_aggregate(
            plan_result="success",
            plan_receipt=plan,
            execution_sha=EXECUTION_SHA,
            lanes=_lanes(),
            receipt_root=receipts,
            timing_path=timings,
        )


def test_aggregate_rejects_selected_lane_that_was_skipped(tmp_path: Path) -> None:
    plan, receipts, timings = _evidence(tmp_path)
    lanes = _lanes()
    lanes["static"] = LaneResult(True, "skipped")

    with pytest.raises(HarborSuiteError, match="static expected success"):
        validate_aggregate(
            plan_result="success",
            plan_receipt=plan,
            execution_sha=EXECUTION_SHA,
            lanes=lanes,
            receipt_root=receipts,
            timing_path=timings,
        )
