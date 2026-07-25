"""Measure the pinned Lean REPL as an exploratory goal-state transport."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import IO, Any

TASKS: tuple[dict[str, Any], ...] = (
    {
        "task_id": "CONJUNCTION-DECOMPOSITION",
        "command": "example (P Q : Prop) (hP : P) (hQ : Q) : P ∧ Q := by sorry",
        "tactics": ("constructor", "exact hP", "exact hQ"),
        "expected_first_goal_count": 2,
    },
    {
        "task_id": "LOCAL-PREMISE-APPLICATION",
        "command": "example (P Q : Prop) (hP : P) (h : P → Q) : Q := by sorry",
        "tactics": ("exact h hP",),
        "expected_first_goal_count": 0,
    },
)


class ReplSpikeError(RuntimeError):
    """The pinned checkout or REPL protocol did not match the spike contract."""


def _read_response(stdout: IO[str]) -> dict[str, Any]:
    lines: list[str] = []
    while True:
        line = stdout.readline()
        if line == "":
            raise ReplSpikeError("Lean REPL closed before returning a response")
        if not line.strip():
            if lines:
                break
            continue
        lines.append(line)
    payload = json.loads("".join(lines))
    if not isinstance(payload, dict):
        raise ReplSpikeError("Lean REPL response must be a JSON object")
    return payload


def _exchange(
    process: subprocess.Popen[str],
    request: Mapping[str, object],
) -> tuple[dict[str, Any], float]:
    if process.stdin is None or process.stdout is None:
        raise ReplSpikeError("Lean REPL pipes are unavailable")
    started = time.monotonic()
    process.stdin.write(json.dumps(request, sort_keys=True) + "\n\n")
    process.stdin.flush()
    response = _read_response(process.stdout)
    return response, time.monotonic() - started


def run_tasks(repl: Path) -> dict[str, Any]:
    started = time.monotonic()
    process = subprocess.Popen(
        [str(repl)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    task_results: list[dict[str, Any]] = []
    try:
        for task in TASKS:
            command_response, command_seconds = _exchange(
                process,
                {"cmd": task["command"]},
            )
            sorries = command_response.get("sorries")
            if not isinstance(sorries, list) or len(sorries) != 1:
                raise ReplSpikeError(
                    f"{task['task_id']} did not expose one proof state"
                )
            proof_state = sorries[0].get("proofState")
            if not isinstance(proof_state, int):
                raise ReplSpikeError(
                    f"{task['task_id']} returned an invalid proof state"
                )
            traces: list[dict[str, Any]] = []
            for tactic in task["tactics"]:
                response, elapsed = _exchange(
                    process,
                    {"tactic": tactic, "proofState": proof_state},
                )
                next_state = response.get("proofState")
                goals = response.get("goals")
                if not isinstance(next_state, int) or not isinstance(goals, list):
                    raise ReplSpikeError(
                        f"{task['task_id']} tactic response is malformed"
                    )
                traces.append(
                    {
                        "tactic": tactic,
                        "elapsed_seconds": round(elapsed, 6),
                        "goal_count": len(goals),
                    }
                )
                proof_state = next_state
            task_results.append(
                {
                    "task_id": task["task_id"],
                    "command_seconds": round(command_seconds, 6),
                    "tactics": traces,
                    "completed": traces[-1]["goal_count"] == 0,
                    "decomposition_observed": (
                        traces[0]["goal_count"] == task["expected_first_goal_count"]
                    ),
                }
            )
    finally:
        if process.stdin is not None:
            process.stdin.close()
        try:
            return_code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            return_code = process.wait(timeout=5)
    stderr = process.stderr.read() if process.stderr is not None else ""
    return {
        "protocol": "leanprover-community/repl",
        "task_count": len(task_results),
        "completed_count": sum(result["completed"] for result in task_results),
        "parameter_error_count": sum(
            "message" in trace for result in task_results for trace in result["tactics"]
        ),
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "return_code": return_code,
        "stderr": stderr,
        "tasks": task_results,
        "limitations": [
            "completed tactic states cannot be replayed into the originating command",
            "the spike measures protocol viability, not agent outcome improvement",
            "final trust still requires lean.check over explicit source",
        ],
    }


def _verify_pin(checkout: Path, pin: Mapping[str, object]) -> None:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if commit != pin.get("commit"):
        raise ReplSpikeError(f"checkout commit {commit} differs from frozen pin")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--repl", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    pin_path = Path(__file__).with_name("lean_repl_pin.json")
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    _verify_pin(args.checkout, pin)
    repl = args.repl or args.checkout / ".lake" / "build" / "bin" / "repl"
    result = {**pin, **run_tasks(repl)}
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if result["completed_count"] == result["task_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
