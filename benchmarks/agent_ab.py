"""Run paired no-tool and Jacobian-capability Codex evaluations.

This benchmark measures whether Jacobian changes agent outcomes. It is
separate from ``agent_mcp.py``, which validates MCP and checker integration.

Run a three-pair pilot with:

    uv run python benchmarks/agent_ab.py --case ERDOS-STRAUS-AB-001
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import statistics
import subprocess
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jacobian.contracts.verification import VerificationRecord
from jacobian.store import ArtifactStore, StoreError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_ROOT = Path(__file__).with_name("ab_cases")
REPORT_SCHEMA = CASES_ROOT / "report.schema.json"
DEFAULT_RESULTS_ROOT = Path(__file__).with_name("results") / "ab"
CONDITIONS = ("control", "treatment")

COMMON_PROMPT = """\
Complete mathematical evaluation case {case_id}.

{prompt}

Return only the required JSON report. Record what work concerned mathematical
strategy in feedback.reasoning_focus, what work concerned constructing or
operating infrastructure in feedback.infrastructure_work, and missing
capabilities in feedback.tooling_gaps. Empty lists are valid. Do not claim
anything beyond the exact finite scope.
"""

CONTROL_INSTRUCTIONS = """\
Jacobian and all MCP servers are unavailable in this condition. You may create
and run local code in the empty workspace to perform the finite check. Report
assurance as SELF_CHECKED and verification_record_uri as null.
"""

TREATMENT_INSTRUCTIONS = """\
Use the jacobian_local MCP server for all mathematical computation. Do not use
shell commands or create programs. Call capability.invoke directly with
reference.solve in VERIFY mode. Its payload uses reference_name
"erdos_straus", predicate {name: "erdos_straus_range", parameters:
{lower_bound: 2, upper_bound: 120}}, candidate {lower_bound: 2, upper_bound:
120}, and witness_role "SUPPORTS_CLAIM". Report VERIFIED only if the capability
returns that assurance, and copy its exact verification_record_uri.
"""


class BenchmarkError(RuntimeError):
    """The A/B runner, report, or known-answer evidence is invalid."""


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BenchmarkError(f"{path} must contain a JSON object")
    return payload


def load_cases(selected: Sequence[str]) -> list[dict[str, Any]]:
    cases = [
        _load_json_object(path)
        for path in sorted(CASES_ROOT.glob("*.json"))
        if path.name != REPORT_SCHEMA.name
    ]
    indexed = {str(case.get("case_id")): case for case in cases}
    if len(indexed) != len(cases):
        raise BenchmarkError("A/B case IDs must be unique")
    if not selected or selected == ["all"]:
        return cases
    missing = sorted(set(selected) - set(indexed))
    if missing:
        raise BenchmarkError(f"unknown A/B cases: {', '.join(missing)}")
    return [indexed[case_id] for case_id in selected]


def parse_transcript(path: Path) -> dict[str, Any]:
    mcp_calls: list[str] = []
    shell_calls: list[str] = []
    usage: dict[str, Any] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "mcp_tool_call"
            and isinstance(item.get("tool"), str)
        ):
            mcp_calls.append(item["tool"])
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "command_execution"
        ):
            command = item.get("command")
            shell_calls.append(command if isinstance(command, str) else "")
        if event.get("type") == "turn.completed" and isinstance(
            event.get("usage"), dict
        ):
            usage = event["usage"]
    return {
        "mcp_calls": mcp_calls,
        "shell_calls": shell_calls,
        "usage": usage,
    }


def score_report(
    case: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    condition: str,
    state_dir: Path,
    mcp_calls: Sequence[str],
) -> dict[str, Any]:
    expected_value = case.get("expected")
    if not isinstance(expected_value, dict):
        raise BenchmarkError("case expected must be an object")
    expected = expected_value
    for field in ("case_id", "conclusion", "checked_count", "first_failure"):
        wanted = case.get(field) if field == "case_id" else expected.get(field)
        if report.get(field) != wanted:
            raise BenchmarkError(f"report {field} differs from the known answer")
    feedback = report.get("feedback")
    if (
        not isinstance(feedback, dict)
        or set(feedback) != {"reasoning_focus", "infrastructure_work", "tooling_gaps"}
        or not all(
            isinstance(value, list) and all(isinstance(item, str) for item in value)
            for value in feedback.values()
        )
    ):
        raise BenchmarkError("report feedback has an invalid structure")

    checks = ["known finite answer", "structured workload feedback"]
    if condition == "control":
        if mcp_calls:
            raise BenchmarkError("control condition used an MCP tool")
        if report.get("assurance") != "SELF_CHECKED":
            raise BenchmarkError("control assurance must be SELF_CHECKED")
        if report.get("verification_record_uri") is not None:
            raise BenchmarkError("control condition reported a verification record")
        checks.append("no-Jacobian control isolation")
    elif condition == "treatment":
        if "capability.invoke" not in mcp_calls:
            raise BenchmarkError("treatment did not invoke a Jacobian capability")
        if report.get("assurance") != "VERIFIED":
            raise BenchmarkError("treatment did not report verified assurance")
        record_uri = report.get("verification_record_uri")
        if not isinstance(record_uri, str):
            raise BenchmarkError("treatment omitted its verification record")
        _score_erdos_record(
            state_dir=state_dir,
            record_uri=record_uri,
            expected=expected,
        )
        checks.append("durable bounded verification record")
    else:
        raise BenchmarkError(f"unknown condition: {condition}")
    return {"passed": True, "checks": checks}


def _score_erdos_record(
    *,
    state_dir: Path,
    record_uri: str,
    expected: Mapping[str, Any],
) -> None:
    store = ArtifactStore(state_dir)
    try:
        record = VerificationRecord.model_validate(store.get(record_uri).payload)
        evidence = store.get(record.evidence_uri)
    except (StoreError, ValueError) as exc:
        raise BenchmarkError("treatment verification record is unavailable") from exc
    if record.conclusion.value != expected.get("conclusion"):
        raise BenchmarkError("verification record has the wrong conclusion")
    payload = evidence.payload
    if not isinstance(payload, dict):
        raise BenchmarkError("verified evidence is malformed")
    witness = payload.get("payload")
    table = witness.get("decompositions") if isinstance(witness, dict) else None
    if not isinstance(table, list):
        raise BenchmarkError("verified decomposition table is missing")
    lower = int(expected["lower_bound"])
    upper = int(expected["upper_bound"])
    seen: set[int] = set()
    for row in table:
        if not isinstance(row, dict):
            raise BenchmarkError("verified decomposition row is malformed")
        try:
            n, x, y, z = (int(row[key]) for key in ("n", "x", "y", "z"))
        except (KeyError, TypeError, ValueError) as exc:
            raise BenchmarkError("verified decomposition row is malformed") from exc
        if min(x, y, z) <= 0:
            raise BenchmarkError("verified denominator is not positive")
        if 4 * x * y * z != n * (x * y + x * z + y * z):
            raise BenchmarkError("verified decomposition identity fails")
        seen.add(n)
    if seen != set(range(lower, upper + 1)):
        raise BenchmarkError("verified evidence has the wrong finite scope")


def _codex_command(
    *,
    codex_command: str,
    condition: str,
    workspace: Path,
    report_path: Path,
    state_dir: Path,
    model: str | None,
    reasoning_effort: str,
) -> list[str]:
    command = [
        codex_command,
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--skip-git-repo-check",
        "--sandbox",
        "workspace-write",
        "--cd",
        str(workspace),
        "--color",
        "never",
        "--json",
        "--output-schema",
        str(REPORT_SCHEMA),
        "--output-last-message",
        str(report_path),
        "-c",
        "model_reasoning_effort=" + json.dumps(reasoning_effort),
    ]
    if condition == "treatment":
        uv_command = shutil.which("uv")
        if uv_command is None:
            raise BenchmarkError("uv is required for the treatment MCP server")
        server_args = [
            "run",
            "--project",
            str(PROJECT_ROOT),
            "jacobian-mcp",
            "--tool-profile",
            "capabilities",
            "--state-dir",
            str(state_dir),
        ]
        command.extend(
            [
                "-c",
                "mcp_servers.jacobian_local.command=" + json.dumps(uv_command),
                "-c",
                "mcp_servers.jacobian_local.args=" + json.dumps(server_args),
                "-c",
                "mcp_servers.jacobian_local.cwd=" + json.dumps(str(PROJECT_ROOT)),
                "-c",
                "mcp_servers.jacobian_local.enabled=true",
                "-c",
                "mcp_servers.jacobian_local.required=true",
                "-c",
                "mcp_servers.jacobian_local.startup_timeout_sec=30",
                "-c",
                "mcp_servers.jacobian_local.tool_timeout_sec=360",
            ]
        )
    if model is not None:
        command.extend(["--model", model])
    command.append("-")
    return command


def _run_condition(
    case: dict[str, Any],
    *,
    condition: str,
    repetition: int,
    pair_root: Path,
    codex_command: str,
    model: str | None,
    reasoning_effort: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    condition_root = pair_root / condition
    workspace = condition_root / "workspace"
    state_dir = condition_root / "state"
    transcript = condition_root / "transcript.jsonl"
    stderr_path = condition_root / "codex.stderr.log"
    report_path = condition_root / "agent-report.json"
    condition_root.mkdir(parents=True)
    workspace.mkdir()
    state_dir.mkdir()
    condition_instructions = (
        CONTROL_INSTRUCTIONS if condition == "control" else TREATMENT_INSTRUCTIONS
    )
    prompt = condition_instructions + "\n" + COMMON_PROMPT.format(**case)
    command = _codex_command(
        codex_command=codex_command,
        condition=condition,
        workspace=workspace,
        report_path=report_path,
        state_dir=state_dir,
        model=model,
        reasoning_effort=reasoning_effort,
    )
    started = time.monotonic()
    started_at = _timestamp()
    try:
        completed = subprocess.run(
            command,
            cwd=workspace,
            env=dict(os.environ),
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        exit_code: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        operational_error = None
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        operational_error = f"Codex exceeded {timeout_seconds} seconds"
    elapsed = time.monotonic() - started
    transcript.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    telemetry = parse_transcript(transcript)
    report: dict[str, Any] | None = None
    if operational_error is not None:
        score = {"passed": False, "error": operational_error}
    elif exit_code != 0:
        score = {"passed": False, "error": f"Codex exited with status {exit_code}"}
    else:
        try:
            report = _load_json_object(report_path)
            score = score_report(
                case,
                report,
                condition=condition,
                state_dir=state_dir,
                mcp_calls=telemetry["mcp_calls"],
            )
        except (BenchmarkError, OSError, json.JSONDecodeError) as exc:
            score = {"passed": False, "error": str(exc)}
    result = {
        "case_id": case["case_id"],
        "case_version": case["version"],
        "condition": condition,
        "repetition": repetition,
        "started_at": started_at,
        "completed_at": _timestamp(),
        "elapsed_seconds": round(elapsed, 3),
        "exit_code": exit_code,
        "usage": telemetry["usage"],
        "mcp_calls": telemetry["mcp_calls"],
        "mcp_call_count": len(telemetry["mcp_calls"]),
        "shell_calls": telemetry["shell_calls"],
        "shell_call_count": len(telemetry["shell_calls"]),
        "workspace_file_count": sum(
            1 for path in workspace.rglob("*") if path.is_file()
        ),
        "agent_report": report,
        "score": score,
    }
    (condition_root / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def summarize_pairs(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_key: dict[tuple[str, int], dict[str, Mapping[str, Any]]] = {}
    for result in results:
        key = (str(result["case_id"]), int(result["repetition"]))
        by_key.setdefault(key, {})[str(result["condition"])] = result
    pairs: list[dict[str, Any]] = []
    for (case_id, repetition), conditions in sorted(by_key.items()):
        if set(conditions) != set(CONDITIONS):
            continue
        control = conditions["control"]
        treatment = conditions["treatment"]
        pairs.append(
            {
                "case_id": case_id,
                "repetition": repetition,
                "control_passed": bool(control["score"].get("passed")),
                "treatment_passed": bool(treatment["score"].get("passed")),
                "elapsed_delta_seconds": round(
                    float(treatment["elapsed_seconds"])
                    - float(control["elapsed_seconds"]),
                    3,
                ),
                "input_token_delta": _usage_value(treatment, "input_tokens")
                - _usage_value(control, "input_tokens"),
                "output_token_delta": _usage_value(treatment, "output_tokens")
                - _usage_value(control, "output_tokens"),
                "shell_call_delta": int(treatment["shell_call_count"])
                - int(control["shell_call_count"]),
                "mcp_call_delta": int(treatment["mcp_call_count"])
                - int(control["mcp_call_count"]),
            }
        )
    condition_summary = {
        condition: _condition_summary(
            [result for result in results if result["condition"] == condition]
        )
        for condition in CONDITIONS
    }
    return {
        "pair_count": len(pairs),
        "conditions": condition_summary,
        "pairs": pairs,
    }


def _condition_summary(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not results:
        return {"runs": 0}
    return {
        "runs": len(results),
        "pass_rate": sum(bool(result["score"].get("passed")) for result in results)
        / len(results),
        "median_elapsed_seconds": statistics.median(
            float(result["elapsed_seconds"]) for result in results
        ),
        "median_input_tokens": statistics.median(
            _usage_value(result, "input_tokens") for result in results
        ),
        "median_output_tokens": statistics.median(
            _usage_value(result, "output_tokens") for result in results
        ),
    }


def _usage_value(result: Mapping[str, Any], field: str) -> int:
    usage = result.get("usage")
    value = usage.get(field, 0) if isinstance(usage, dict) else 0
    return int(value) if isinstance(value, int | float) else 0


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _run_text(command: Sequence[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return completed.stdout.strip()


def _digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run paired Codex control and Jacobian capability evaluations."
    )
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--model")
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high"),
        default="medium",
    )
    parser.add_argument("--codex-command", default="codex")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--order-seed", type=int, default=0)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_ROOT)
    args = parser.parse_args(argv)
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")
    cases = load_cases(args.case)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_root = args.output_dir.resolve() / run_id
    run_root.mkdir(parents=True)
    metadata = {
        "benchmark": "jacobian-agent-capability-ab",
        "repository_commit": _run_text(["git", "rev-parse", "HEAD"]),
        "repository_dirty": bool(_run_text(["git", "status", "--porcelain"])),
        "dependency_lock_digest": _digest_file(PROJECT_ROOT / "uv.lock"),
        "codex_version": _run_text([args.codex_command, "--version"]),
        "requested_model": args.model or "configured-default",
        "reasoning_effort": args.reasoning_effort,
        "order_seed": args.order_seed,
    }
    randomizer = random.Random(args.order_seed)
    results: list[dict[str, Any]] = []
    for case in cases:
        for repetition in range(1, args.repetitions + 1):
            order = list(CONDITIONS)
            randomizer.shuffle(order)
            pair_root = (
                run_root / str(case["case_id"]).lower() / f"repetition-{repetition:02d}"
            )
            for condition in order:
                results.append(
                    _run_condition(
                        case,
                        condition=condition,
                        repetition=repetition,
                        pair_root=pair_root,
                        codex_command=args.codex_command,
                        model=args.model,
                        reasoning_effort=args.reasoning_effort,
                        timeout_seconds=args.timeout_seconds,
                    )
                )
    summary = {
        **metadata,
        "run_id": run_id,
        "started_conditions": len(results),
        **summarize_pairs(results),
    }
    (run_root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if all(result["score"].get("passed") for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
