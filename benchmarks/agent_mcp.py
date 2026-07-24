"""Run public known-answer cases through a real Codex CLI and Jacobian MCP.

This is an agent-behavior pilot, not a mathematical verifier or a performance
benchmark. The scorer distrusts the agent's prose and validates the durable
verification record, evidence, bindings, claim, and candidate in the isolated
Jacobian state directory.

Run with:

    uv run python benchmarks/agent_mcp.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jacobian.store import ArtifactStore, StoreError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_ROOT = Path(__file__).with_name("agent_cases")
DEFAULT_RESULTS_ROOT = Path(__file__).with_name("results")
REPORT_SCHEMA = CASES_ROOT / "report.schema.json"
ARTIFACT_PREFIX = "artifact://sha256/"

SYSTEM_TASK = """\
Use only the jacobian_local MCP tools and resources for the mathematical work.
Do not run shell commands, read repository files, edit files, or use network
retrieval. Start with {agent_contract_uri}; it contains the selected domain's
compact input contract and exact semantic identity. Treat evaluation and
witness search as
UNVERIFIED. A decisive result is VERIFIED only after the compatible independent
checker accepts the exact bound evidence. Do not reread returned evidence or
verification-record resources merely to prepare the final report; the benchmark
scorer validates them directly. For bundled witness cases, use verification.run
instead of manually calling its five component tools.

Complete public known-answer case {case_id}. Set report case_id exactly to
{case_id}.

{prompt}

Return the required JSON report. Report the exact durable URIs returned by the
tools. Do not infer verification from operational completion, exhaustive
evaluation, or failure to find a witness. State any remaining limitations.
Record concise feedback grounded in this run: useful tooling, tooling gaps,
missing domain knowledge, and concrete improvements. Empty feedback lists are
valid when the run exposed no issue.
"""


class BenchmarkError(RuntimeError):
    """The runner or durable benchmark evidence is invalid."""


def _load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BenchmarkError(f"{path} must contain a JSON object")
    return value


def load_cases(selected: Sequence[str]) -> list[dict[str, Any]]:
    cases = [
        _load_json_object(path)
        for path in sorted(CASES_ROOT.glob("*.json"))
        if path.name != REPORT_SCHEMA.name
    ]
    by_id = {str(case.get("case_id")): case for case in cases}
    if len(by_id) != len(cases):
        raise BenchmarkError("agent benchmark case IDs must be unique")
    if not selected or selected == ["all"]:
        return cases
    missing = sorted(set(selected) - set(by_id))
    if missing:
        raise BenchmarkError(f"unknown agent benchmark cases: {', '.join(missing)}")
    return [by_id[case_id] for case_id in selected]


def _run_text(command: Sequence[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return completed.stdout.strip()


def _digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _artifact_uri(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith(ARTIFACT_PREFIX)
        or len(value.removeprefix(ARTIFACT_PREFIX)) != 64
    ):
        raise BenchmarkError(f"agent report has an invalid {field}")
    return value


def parse_transcript(path: Path) -> tuple[list[str], dict[str, Any] | None]:
    calls: list[str] = []
    usage: dict[str, Any] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if (
            isinstance(event, dict)
            and event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "mcp_tool_call"
            and isinstance(item.get("tool"), str)
        ):
            calls.append(item["tool"])
        if (
            isinstance(event, dict)
            and event.get("type") == "turn.completed"
            and isinstance(event.get("usage"), dict)
        ):
            usage = event["usage"]
    return calls, usage


def _as_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BenchmarkError(f"{field} must be an object")
    return value


def _as_pairs(value: Any, field: str) -> set[tuple[str, str]]:
    if not isinstance(value, list):
        raise BenchmarkError(f"{field} must be a list")
    try:
        return {(str(item[0]), str(item[1])) for item in value}
    except (IndexError, TypeError) as exc:
        raise BenchmarkError(f"{field} contains an invalid pair") from exc


def _as_paths(value: Any, field: str) -> set[tuple[str, ...]]:
    if not isinstance(value, list):
        raise BenchmarkError(f"{field} must be a list")
    try:
        return {tuple(str(part) for part in item) for item in value}
    except TypeError as exc:
        raise BenchmarkError(f"{field} contains an invalid path") from exc


def _integer_matrix(value: Any) -> list[list[int]]:
    if not isinstance(value, list):
        raise BenchmarkError("matrix entries must be a list")
    try:
        return [[int(entry) for entry in row] for row in value]
    except (TypeError, ValueError) as exc:
        raise BenchmarkError("matrix entries must be exact integers") from exc


def _check_candidate(
    actual: dict[str, Any],
    expected: Mapping[str, Any],
) -> None:
    kind = expected.get("kind")
    if kind in {"graph", "graph_paths"}:
        if set(map(str, actual.get("vertices", ()))) != set(expected["vertices"]):
            raise BenchmarkError("candidate vertices differ from the case")
        if _as_pairs(actual.get("arcs"), "candidate arcs") != _as_pairs(
            expected["arcs"],
            "expected arcs",
        ):
            raise BenchmarkError("candidate arcs differ from the case")
        if kind == "graph_paths":
            if actual.get("source") != expected["source"]:
                raise BenchmarkError("candidate source differs from the case")
            if set(map(str, actual.get("terminals", ()))) != set(expected["terminals"]):
                raise BenchmarkError("candidate terminals differ from the case")
            if _as_paths(
                actual.get("intended_paths"),
                "candidate intended paths",
            ) != _as_paths(expected["intended_paths"], "expected intended paths"):
                raise BenchmarkError("candidate intended paths differ from the case")
        return
    if kind == "matrix":
        if (
            actual.get("rows") != expected["rows"]
            or actual.get("cols") != expected["cols"]
        ):
            raise BenchmarkError("candidate matrix dimensions differ from the case")
        if _integer_matrix(actual.get("entries")) != expected["entries"]:
            raise BenchmarkError("candidate matrix entries differ from the case")
        return
    if kind == "lean":
        if actual.get("statement") != expected.get("statement"):
            raise BenchmarkError("Lean candidate statement differs from the case")
        if actual.get("environment") != expected.get("environment", "CORE"):
            raise BenchmarkError("Lean candidate environment differs from the case")
        proof = actual.get("proof")
        if not isinstance(proof, str) or not proof.strip():
            raise BenchmarkError("Lean candidate proof is empty")
        return
    if kind == "integer_range":
        if actual.get("lower_bound") != expected.get("lower_bound") or actual.get(
            "upper_bound"
        ) != expected.get("upper_bound"):
            raise BenchmarkError("candidate integer range differs from the case")
        return
    raise BenchmarkError(f"unsupported candidate expectation kind: {kind!r}")


def _check_claim(
    actual: dict[str, Any],
    expected: Mapping[str, Any],
) -> None:
    candidate = _as_object(expected.get("candidate"), "expected candidate")
    if candidate.get("kind") == "lean":
        if actual.get("statement") != candidate.get("statement"):
            raise BenchmarkError("Lean claim statement differs from the case")
        if actual.get("environment") != candidate.get("environment", "CORE"):
            raise BenchmarkError("Lean claim environment differs from the case")
        if actual.get("allowed_axioms") != expected.get("allowed_axioms", []):
            raise BenchmarkError("Lean claim has an unexpected trust base")
        return
    predicate = _as_object(actual.get("predicate"), "claim predicate")
    if actual.get("domain_id") != expected.get("domain_id"):
        raise BenchmarkError("claim domain differs from the case")
    if predicate.get("name") != expected.get("predicate"):
        raise BenchmarkError("claim predicate differs from the case")
    if "parameters" in expected and predicate.get("parameters") != expected.get(
        "parameters"
    ):
        raise BenchmarkError("claim predicate parameters differ from the case")


def _check_evidence(
    evidence: dict[str, Any],
    candidate: dict[str, Any],
    expected: Mapping[str, Any],
) -> str:
    evidence_kind = str(expected.get("evidence_kind", "WITNESS"))
    if evidence_kind == "WITNESS":
        if evidence.get("witness_format") != expected.get("witness_format"):
            raise BenchmarkError("witness format differs from the case")
        accepted_payloads = expected.get("accepted_witness_payloads")
        if (
            accepted_payloads is not None
            and evidence.get("payload") not in accepted_payloads
        ):
            raise BenchmarkError("witness payload does not match the public oracle")
        if expected.get("witness_format") == "erdos_straus.decomposition_table":
            payload = _as_object(evidence.get("payload"), "witness payload")
            table = payload.get("decompositions")
            if not isinstance(table, list):
                raise BenchmarkError("Erdős-Straus witness table is missing")
            expected_candidate = _as_object(
                expected.get("candidate"),
                "expected candidate",
            )
            expected_ns = set(
                range(
                    int(expected_candidate["lower_bound"]),
                    int(expected_candidate["upper_bound"]) + 1,
                )
            )
            actual_ns: set[int] = set()
            for row_value in table:
                row = _as_object(row_value, "Erdős-Straus witness row")
                try:
                    n, x, y, z = (
                        int(row["n"]),
                        int(row["x"]),
                        int(row["y"]),
                        int(row["z"]),
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise BenchmarkError(
                        "Erdős-Straus witness row is malformed"
                    ) from exc
                if min(x, y, z) <= 0:
                    raise BenchmarkError(
                        "Erdős-Straus witness has a nonpositive denominator"
                    )
                if 4 * x * y * z != n * (x * y + x * z + y * z):
                    raise BenchmarkError(
                        "Erdős-Straus witness fails the exact identity"
                    )
                if n in actual_ns:
                    raise BenchmarkError("Erdős-Straus witness contains duplicate n")
                actual_ns.add(n)
            if actual_ns != expected_ns:
                raise BenchmarkError(
                    "Erdős-Straus witness does not cover the exact range"
                )
        return evidence_kind
    if evidence_kind == "CERTIFICATE":
        if evidence.get("certificate_type") != expected.get("certificate_type"):
            raise BenchmarkError("certificate format differs from the case")
        payload = _as_object(evidence.get("payload"), "certificate payload")
        if candidate.get("statement") != payload.get("statement") or candidate.get(
            "proof"
        ) != payload.get("proof"):
            raise BenchmarkError("Lean certificate source differs from the candidate")
        if candidate.get("environment") != payload.get("environment"):
            raise BenchmarkError(
                "Lean certificate environment differs from the candidate"
            )
        if payload.get("allowed_axioms") != expected.get("allowed_axioms", []):
            raise BenchmarkError("Lean certificate has an unexpected trust base")
        return evidence_kind
    raise BenchmarkError(f"unsupported evidence kind: {evidence_kind}")


def score_run(
    case: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    state_dir: Path,
    tool_calls: Sequence[str],
) -> dict[str, Any]:
    expected = _as_object(case.get("expected"), "case expected")
    checks: list[str] = []
    if report.get("case_id") != case.get("case_id"):
        raise BenchmarkError("agent report case_id does not match the case")
    if report.get("conclusion") != expected.get("conclusion"):
        raise BenchmarkError("agent report conclusion does not match the oracle")
    if report.get("evaluation_verification") != "UNVERIFIED":
        raise BenchmarkError("evaluation was not reported as UNVERIFIED")
    if report.get("witness_search_verification") != "UNVERIFIED":
        raise BenchmarkError("witness search was not reported as UNVERIFIED")
    if report.get("final_verification") != "VERIFIED":
        raise BenchmarkError("final result was not reported as VERIFIED")
    checks.append("agent assurance labels")

    feedback = _as_object(report.get("feedback"), "agent feedback")
    feedback_fields = {
        "tooling_strengths",
        "tooling_gaps",
        "domain_knowledge_gaps",
        "suggested_improvements",
    }
    if set(feedback) != feedback_fields or not all(
        isinstance(feedback[field], list)
        and all(isinstance(item, str) for item in feedback[field])
        for field in feedback_fields
    ):
        raise BenchmarkError("agent feedback has an invalid structure")
    checks.append("structured agent feedback")

    required_tools = case.get("required_tools")
    if not isinstance(required_tools, list) or not all(
        isinstance(tool, str) for tool in required_tools
    ):
        raise BenchmarkError("case required_tools must be a string list")
    missing_tools = sorted(set(required_tools) - set(tool_calls))
    if missing_tools:
        raise BenchmarkError(
            f"transcript is missing MCP calls: {', '.join(missing_tools)}"
        )
    checks.append("required MCP tool sequence")

    claim_uri = _artifact_uri(report.get("claim_uri"), "claim_uri")
    candidate_uri = _artifact_uri(report.get("candidate_uri"), "candidate_uri")
    evidence_uri = _artifact_uri(report.get("evidence_uri"), "evidence_uri")
    record_uri = _artifact_uri(
        report.get("verification_record_uri"),
        "verification_record_uri",
    )
    store = ArtifactStore(state_dir)
    try:
        claim = store.get(claim_uri)
        candidate = store.get(candidate_uri)
        evidence = store.get(evidence_uri)
        record = store.get(record_uri)
        semantics = store.get(claim.manifest.semantics_uri)
    except StoreError as exc:
        raise BenchmarkError("reported artifact URI is unavailable") from exc

    claim_payload = _as_object(claim.payload, "claim payload")
    _check_claim(claim_payload, expected)
    candidate_payload = _as_object(candidate.payload, "candidate payload")
    _check_candidate(
        candidate_payload,
        _as_object(expected.get("candidate"), "expected candidate"),
    )
    checks.append("known case claim and candidate")

    evidence_payload = _as_object(evidence.payload, "evidence payload")
    record_payload = _as_object(record.payload, "verification record")
    evidence_kind = _check_evidence(
        evidence_payload,
        candidate_payload,
        expected,
    )
    if (
        record_payload.get("conclusion") != expected.get("conclusion")
        or record_payload.get("evidence_kind") != evidence_kind
        or record_payload.get("evidence_uri") != evidence_uri
    ):
        raise BenchmarkError("verification record does not bind the expected result")
    checks.append("known-answer evidence and verification record")

    bindings = _as_object(record_payload.get("bindings"), "record bindings")
    if bindings != evidence_payload.get("bindings"):
        raise BenchmarkError("record and witness bindings differ")
    if bindings.get("claim_digest") != claim.manifest.object_digest:
        raise BenchmarkError("verification record is bound to another claim")
    if bindings.get("candidate_digest") != candidate.manifest.object_digest:
        raise BenchmarkError("verification record is bound to another candidate")
    if bindings.get("semantics_digest") != semantics.manifest.object_digest:
        raise BenchmarkError("verification record is bound to other semantics")
    checks.append("claim, candidate, semantics, and evidence bindings")

    return {
        "passed": True,
        "checks": checks,
        "case_id": case["case_id"],
        "verification_record_uri": record_uri,
        "evidence_uri": evidence_uri,
    }


def _run_case(
    case: dict[str, Any],
    *,
    run_root: Path,
    codex_command: str,
    model: str | None,
    reasoning_effort: str,
    timeout_seconds: int,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    case_id = str(case["case_id"])
    case_root = run_root / case_id.lower()
    state_dir = case_root / "state"
    transcript = case_root / "transcript.jsonl"
    stderr_path = case_root / "codex.stderr.log"
    report_path = case_root / "agent-report.json"
    feedback_path = case_root / "feedback.json"
    case_root.mkdir(parents=True)
    state_dir.mkdir()
    prompt = SYSTEM_TASK.format(
        agent_contract_uri=f"reference://domain/{case['reference_name']}",
        case_id=case_id,
        prompt=case["prompt"],
    )
    command = [
        codex_command,
        "exec",
        "--ephemeral",
        "--sandbox",
        "workspace-write",
        "--color",
        "never",
        "--json",
        "--output-schema",
        str(REPORT_SCHEMA),
        "--output-last-message",
        str(report_path),
        "-c",
        "mcp_servers.jacobian_local.env.JACOBIAN_STATE_DIR="
        + json.dumps(str(state_dir)),
        "-c",
        "model_reasoning_effort=" + json.dumps(reasoning_effort),
    ]
    if model is not None:
        command.extend(["--model", model])
    command.append("-")
    environment = dict(os.environ)
    environment["JACOBIAN_STATE_DIR"] = str(state_dir)

    started_at = _timestamp()
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            env=environment,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        exit_code: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        operational_error: str | None = None
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        operational_error = f"Codex exceeded {timeout_seconds} seconds"
    elapsed = time.monotonic() - started
    transcript.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    tool_calls, usage = parse_transcript(transcript)

    score: dict[str, Any]
    report: dict[str, Any] | None = None
    if operational_error is not None:
        score = {"passed": False, "error": operational_error}
    elif exit_code != 0:
        score = {"passed": False, "error": f"Codex exited with status {exit_code}"}
    else:
        try:
            report = _load_json_object(report_path)
            feedback = _as_object(report.get("feedback"), "agent feedback")
            feedback_path.write_text(
                json.dumps(feedback, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            score = score_run(
                case,
                report,
                state_dir=state_dir,
                tool_calls=tool_calls,
            )
        except (BenchmarkError, OSError, json.JSONDecodeError) as exc:
            score = {"passed": False, "error": str(exc)}

    result = {
        **metadata,
        "case_id": case_id,
        "case_version": case["version"],
        "condition": "kernel",
        "started_at": started_at,
        "completed_at": _timestamp(),
        "elapsed_seconds": round(elapsed, 3),
        "exit_code": exit_code,
        "tool_calls": tool_calls,
        "tool_call_count": len(tool_calls),
        "usage": usage,
        "agent_report": report,
        "score": score,
        "artifacts": {
            "state_dir": str(state_dir.relative_to(run_root)),
            "transcript": str(transcript.relative_to(run_root)),
            "stderr": str(stderr_path.relative_to(run_root)),
            "agent_report": str(report_path.relative_to(run_root)),
            "feedback": str(feedback_path.relative_to(run_root)),
        },
    }
    (case_root / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run public Jacobian cases through a real Codex MCP client.",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="case ID to run; repeat or use 'all' (default)",
    )
    parser.add_argument("--model", help="optional Codex model override")
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high"),
        default="medium",
        help="Codex reasoning budget; fixed explicitly for comparable runs",
    )
    parser.add_argument("--codex-command", default="codex")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_RESULTS_ROOT,
    )
    args = parser.parse_args(argv)
    cases = load_cases(args.case)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_root = args.output_dir.resolve() / run_id
    run_root.mkdir(parents=True)
    metadata = {
        "benchmark": "jacobian-agent-mcp-known-answer-pilot",
        "repository_commit": _run_text(["git", "rev-parse", "HEAD"]),
        "repository_dirty": bool(_run_text(["git", "status", "--porcelain"])),
        "dependency_lock_digest": _digest_file(PROJECT_ROOT / "uv.lock"),
        "codex_version": _run_text([args.codex_command, "--version"]),
        "requested_model": args.model or "configured-default",
        "reasoning_effort": args.reasoning_effort,
        "random_seed_policy": "provider-controlled; no Codex seed option",
    }
    results = [
        _run_case(
            case,
            run_root=run_root,
            codex_command=args.codex_command,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            timeout_seconds=args.timeout_seconds,
            metadata=metadata,
        )
        for case in cases
    ]
    summary = {
        **metadata,
        "run_id": run_id,
        "condition": "kernel",
        "cases": [
            {
                "case_id": result["case_id"],
                "passed": result["score"].get("passed", False),
                "elapsed_seconds": result["elapsed_seconds"],
                "tool_call_count": result["tool_call_count"],
                "error": result["score"].get("error"),
            }
            for result in results
        ],
        "passed": all(result["score"].get("passed", False) for result in results),
    }
    summary_path = run_root / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(summary_path)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
