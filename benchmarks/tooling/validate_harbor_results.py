#!/usr/bin/env python3
"""Fail-closed validation and evidence capture for a Harbor Oracle result."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.tooling.harbor_suite import (  # noqa: E402
    ROOT,
    HarborSuiteError,
    get_suite,
    task_digest,
)


def _task_id(name: Any) -> str:
    return name.rsplit("/", 1)[-1] if isinstance(name, str) else ""


def _validate_payload(
    payload: Any,
    *,
    expected_tasks: set[str],
    expected_digests: dict[str, str],
) -> list[str]:
    failures: list[str] = []
    if not isinstance(payload, dict):
        return ["result.json must contain an object"]
    for key in ("id", "started_at", "finished_at", "n_total_trials", "stats"):
        if key not in payload:
            failures.append(f"result.json: missing {key}")
    total = payload.get("n_total_trials")
    if not isinstance(total, int) or total <= 0:
        failures.append("result.json: n_total_trials must be positive")
    stats = payload.get("stats")
    if not isinstance(stats, dict):
        failures.append("result.json: stats must be an object")
        stats = {}
    for key in (
        "n_completed_trials",
        "n_errored_trials",
        "n_running_trials",
        "n_pending_trials",
        "n_cancelled_trials",
    ):
        value = stats.get(key, 0)
        if not isinstance(value, int) or value < 0:
            failures.append(f"result.json: stats.{key} must be non-negative")
    if any(
        stats.get(key, 0)
        for key in (
            "n_errored_trials",
            "n_running_trials",
            "n_pending_trials",
            "n_cancelled_trials",
        )
    ):
        failures.append("result.json: execution is incomplete or contains errors")

    trials = payload.get("trial_results")
    if not isinstance(trials, list) or not trials:
        failures.append("result.json: trial_results is missing or empty")
        trials = []
    if isinstance(total, int) and len(trials) != total:
        failures.append(
            "result.json: trial_results count disagrees with n_total_trials"
        )
    if stats.get("n_completed_trials", 0) != len(trials):
        failures.append(
            "result.json: completed-trial count disagrees with trial_results"
        )

    observed_tasks: set[str] = set()
    for index, trial in enumerate(trials):
        if not isinstance(trial, dict):
            failures.append(f"trial_results[{index}] must be an object")
            continue
        task_id = _task_id(trial.get("task_name"))
        if not task_id:
            failures.append(f"trial_results[{index}]: missing task_name")
            continue
        observed_tasks.add(task_id)
        if task_id not in expected_tasks:
            failures.append(f"trial_results[{index}]: unexpected task {task_id}")
        checksum = str(trial.get("task_checksum", ""))
        expected = expected_digests.get(task_id)
        if expected and checksum.removeprefix("sha256:") != expected.removeprefix(
            "sha256:"
        ):
            failures.append(
                f"trial_results[{index}]: task digest mismatch for {task_id}"
            )
        if trial.get("exception_info") is not None:
            failures.append(
                f"trial_results[{index}]: exception result is not certifying"
            )
        verifier = trial.get("verifier_result")
        rewards = verifier.get("rewards") if isinstance(verifier, dict) else None
        if not isinstance(rewards, dict) or not rewards:
            failures.append(f"trial_results[{index}]: incomplete verifier reward")
        elif any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            for value in rewards.values()
        ):
            failures.append(f"trial_results[{index}]: verifier reward is not finite")
    if observed_tasks != expected_tasks:
        failures.append(
            "result.json: task coverage differs from requested tasks: "
            f"expected={sorted(expected_tasks)}, observed={sorted(observed_tasks)}"
        )
    return failures


def _find_result(jobs_dir: Path) -> Path:
    candidates = sorted(
        (path for path in jobs_dir.glob("*/result.json") if path.is_file()),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    if not candidates:
        raise HarborSuiteError(f"no Harbor result.json found below {jobs_dir}")
    return candidates[0]


def _git_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def validate(
    *,
    dataset: str,
    tasks: tuple[str, ...] | None,
    jobs_dir: Path,
    result_path: Path | None = None,
) -> Path:
    suite = get_suite(dataset)
    known = {ref.path.name: ref for ref in suite.tasks}
    requested = set(tasks) if tasks else set(known)
    unknown = sorted(requested - set(known))
    if unknown:
        raise HarborSuiteError(f"unknown task(s) for {dataset}: {', '.join(unknown)}")
    result_path = result_path or _find_result(jobs_dir)
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HarborSuiteError(
            f"unable to read Harbor result {result_path}: {exc}"
        ) from exc
    expected_digests = {
        task_id: task_digest(ref.path)
        for task_id, ref in known.items()
        if task_id in requested
    }
    failures = _validate_payload(
        payload,
        expected_tasks=requested,
        expected_digests=expected_digests,
    )
    if failures:
        raise HarborSuiteError("\n".join(failures))
    evidence = result_path.parent / "oracle-evidence.json"
    evidence.write_text(
        json.dumps(
            {
                "source_sha": _git_sha(),
                "harbor_version": importlib.metadata.version("harbor"),
                "dataset": suite.id,
                "tasks": [
                    {
                        "task": task_id,
                        "digest": expected_digests[task_id],
                        "verifier": (
                            ROOT
                            / "benchmarks"
                            / "tasks"
                            / task_id
                            / "tests"
                            / "verifier.py"
                        )
                        .relative_to(ROOT)
                        .as_posix(),
                        "verifier_sha256": hashlib.sha256(
                            (
                                ROOT
                                / "benchmarks"
                                / "tasks"
                                / task_id
                                / "tests"
                                / "verifier.py"
                            ).read_bytes()
                        ).hexdigest(),
                    }
                    for task_id in sorted(requested)
                ],
                "result": result_path.relative_to(ROOT).as_posix(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--tasks", nargs="*")
    parser.add_argument("--jobs-dir", type=Path, required=True)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    try:
        evidence = validate(
            dataset=args.dataset,
            tasks=tuple(args.tasks) if args.tasks else None,
            jobs_dir=args.jobs_dir,
            result_path=args.result,
        )
    except HarborSuiteError as exc:
        parser.error(str(exc))
    print(evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
