"""Plan and run public answer-visible research challenges with Jacobian.

The runner is deliberately separate from scored A/B evaluations. It passes the
published prompt unchanged and always starts Jacobian under the compute/verify
no-retrieval capability policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import subprocess
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from jacobian.canonical import canonicalize_json
from jacobian.capabilities import CapabilityPolicy, CapabilityPolicyProfile
from jacobian.eval_telemetry import parse_agent_transcript
from jacobian.runtime import CheckerAuthorityMode, create_runtime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHALLENGE_ROOT = Path(__file__).with_name("research_challenges")
DEFAULT_SUITE = CHALLENGE_ROOT / "public_postdoc_frontier_v1.json"
CHALLENGE_SCHEMA = CHALLENGE_ROOT / "public_postdoc.schema.json"
DEFAULT_RESULTS_ROOT = Path(__file__).with_name("results") / "research-challenges"
CAPABILITY_POLICY_PROFILE: CapabilityPolicyProfile = "COMPUTE_VERIFY_NO_RETRIEVAL"


class ChallengeRunnerError(ValueError):
    """Raised when a public challenge dispatch cannot be constructed."""


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChallengeRunnerError(f"cannot load JSON from {path}") from exc
    if not isinstance(value, dict):
        raise ChallengeRunnerError(f"{path} must contain one JSON object")
    return value


def load_suite(path: Path) -> dict[str, Any]:
    """Load and validate one immutable public challenge suite."""

    suite = _load_json_object(path)
    schema = _load_json_object(CHALLENGE_SCHEMA)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(suite), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.path) or "<root>"
        raise ChallengeRunnerError(
            f"{path} does not match the public challenge schema at "
            f"{location}: {first.message}"
        )
    return suite


def select_cases(
    suite: Mapping[str, Any],
    *,
    challenge_ids: Sequence[str],
    sample_size: int | None,
    seed: int,
) -> list[dict[str, Any]]:
    cases = suite.get("cases")
    if not isinstance(cases, list):
        raise ChallengeRunnerError("suite cases are malformed")
    indexed = {
        case["challenge_id"]: case
        for case in cases
        if isinstance(case, dict) and isinstance(case.get("challenge_id"), str)
    }
    if challenge_ids:
        unknown = sorted(set(challenge_ids) - set(indexed))
        if unknown:
            raise ChallengeRunnerError("unknown challenge IDs: " + ", ".join(unknown))
        return [indexed[challenge_id] for challenge_id in challenge_ids]
    if sample_size is None:
        raise ChallengeRunnerError(
            "select at least one --challenge or provide --sample-size"
        )
    if sample_size < 1 or sample_size > len(indexed):
        raise ChallengeRunnerError(
            f"--sample-size must be between 1 and {len(indexed)}"
        )
    randomizer = random.Random(seed)
    selected_ids = randomizer.sample(sorted(indexed), sample_size)
    return [indexed[challenge_id] for challenge_id in selected_ids]


def _digest_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _digest_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _run_text(command: Sequence[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return completed.stdout.strip()


def _portfolio_snapshot(policy: CapabilityPolicy) -> dict[str, Any]:
    with (
        TemporaryDirectory(prefix="jacobian-frontier-catalog-") as state_root,
        create_runtime(
            Path(state_root),
            checker_authority=CheckerAuthorityMode.INSTALL_BUNDLED,
            capability_policy=policy,
        ) as runtime,
    ):
        catalog = runtime.core.capabilities.catalog()
    catalog_payload = {
        "catalog_version": catalog.catalog_version,
        "capabilities": [
            descriptor.model_dump(mode="json") for descriptor in catalog.capabilities
        ],
    }
    return {
        "catalog_version": catalog.catalog_version,
        "catalog_digest": (
            "sha256:" + hashlib.sha256(canonicalize_json(catalog_payload)).hexdigest()
        ),
        "capability_count": len(catalog.capabilities),
        "policy_profile": catalog.policy_profile,
        "policy_digest": catalog.policy_digest,
    }


def build_dispatch_plan(
    *,
    suite_path: Path,
    suite: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
    repetitions: int,
    model: str | None,
    reasoning_effort: str,
    timeout_seconds: int,
    seed: int,
) -> dict[str, Any]:
    model_run_count = len(cases) * repetitions
    policy = CapabilityPolicy(profile=CAPABILITY_POLICY_PROFILE)
    portfolio_snapshot = _portfolio_snapshot(policy)
    return {
        "mode": "plan",
        "evaluation_class": "PUBLIC_ANSWER_VISIBLE_DIAGNOSTIC",
        "scored": False,
        "suite_id": suite["suite_id"],
        "suite_version": suite["suite_version"],
        "suite_path": str(suite_path),
        "suite_digest": _digest_file(suite_path),
        "repository_commit": _run_text(["git", "rev-parse", "HEAD"]),
        "repository_dirty": bool(_run_text(["git", "status", "--porcelain"])),
        "portfolio_snapshot": portfolio_snapshot,
        "cases": [
            {
                "challenge_id": case["challenge_id"],
                "prompt_sha256": _digest_text(str(case["prompt"])),
                "repetitions": repetitions,
            }
            for case in cases
        ],
        "sample_seed": seed,
        "model": model or "configured-default",
        "reasoning_effort": reasoning_effort,
        "capability_policy_profile": policy.profile,
        "capability_policy_digest": policy.digest,
        "retrieval_capabilities_available": False,
        "model_run_count": model_run_count,
        "timeout_seconds_per_run": timeout_seconds,
        "maximum_model_wall_seconds": model_run_count * timeout_seconds,
        "execution_requested": False,
    }


def _codex_command(
    *,
    codex_command: str,
    workspace: Path,
    final_path: Path,
    state_dir: Path,
    model: str | None,
    reasoning_effort: str,
) -> list[str]:
    uv_command = shutil.which("uv")
    if uv_command is None:
        raise ChallengeRunnerError("uv is required for the Jacobian MCP server")
    server_args = [
        "run",
        "--project",
        str(PROJECT_ROOT),
        "jacobian-mcp",
        "--state-dir",
        str(state_dir),
        "--capability-policy-profile",
        CAPABILITY_POLICY_PROFILE,
    ]
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
        "--output-last-message",
        str(final_path),
        "-c",
        "model_reasoning_effort=" + json.dumps(reasoning_effort),
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
        "mcp_servers.jacobian_local.startup_timeout_sec=120",
        "-c",
        "mcp_servers.jacobian_local.tool_timeout_sec=360",
    ]
    if model is not None:
        command.extend(["--model", model])
    command.append("-")
    return command


def _run_case(
    case: Mapping[str, Any],
    *,
    repetition: int,
    run_root: Path,
    codex_command: str,
    model: str | None,
    reasoning_effort: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    case_root = (
        run_root / str(case["challenge_id"]).lower() / f"repetition-{repetition:02d}"
    )
    workspace = case_root / "workspace"
    state_dir = case_root / "state"
    transcript_path = case_root / "transcript.jsonl"
    stderr_path = case_root / "codex.stderr.log"
    final_path = case_root / "final.md"
    workspace.mkdir(parents=True)
    state_dir.mkdir()
    command = _codex_command(
        codex_command=codex_command,
        workspace=workspace,
        final_path=final_path,
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
            input=str(case["prompt"]),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        exit_code: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        termination_reason = "COMPLETED"
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        termination_reason = "TIMEOUT"
    elapsed = time.monotonic() - started
    transcript_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    telemetry = parse_agent_transcript(transcript_path)
    artifact_uris = sorted(
        {
            artifact_uri
            for invocation in telemetry["capability_invocations"]
            for artifact_uri in invocation.get("artifact_uris") or ()
            if isinstance(artifact_uri, str)
        }
    )
    return {
        "challenge_id": case["challenge_id"],
        "repetition": repetition,
        "prompt_sha256": _digest_text(str(case["prompt"])),
        "prompt_passed_unchanged": True,
        "capability_policy_profile": CAPABILITY_POLICY_PROFILE,
        "started_at": started_at,
        "completed_at": _timestamp(),
        "elapsed_seconds": round(elapsed, 3),
        "exit_code": exit_code,
        "termination_reason": termination_reason,
        "usage": telemetry["usage"],
        "mcp_calls": telemetry["mcp_calls"],
        "capability_ids": telemetry["capability_ids"],
        "artifact_uris": artifact_uris,
        "tool_error_count": telemetry["tool_error_count"],
        "parameter_error_count": telemetry["parameter_error_count"],
        "mcp_wire_bytes": telemetry["mcp_wire_bytes"],
        "mcp_model_visible_bytes": telemetry["mcp_model_visible_bytes"],
        "mcp_logical_payload_bytes": telemetry["mcp_logical_payload_bytes"],
        "artifact_root": str(state_dir),
        "final_path": str(final_path),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Plan a public research-challenge run. Execution requires --execute "
            "and an explicit --max-model-runs budget."
        )
    )
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--challenge", action="append", default=[])
    parser.add_argument("--sample-size", type=int)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--model")
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high", "xhigh"),
        default="xhigh",
    )
    parser.add_argument("--codex-command", default="codex")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_ROOT)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-model-runs", type=int)
    args = parser.parse_args(argv)
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")
    if args.challenge and args.sample_size is not None:
        parser.error("--challenge and --sample-size are mutually exclusive")
    try:
        suite_path = args.suite.resolve()
        suite = load_suite(suite_path)
        cases = select_cases(
            suite,
            challenge_ids=args.challenge,
            sample_size=args.sample_size,
            seed=args.seed,
        )
        plan = build_dispatch_plan(
            suite_path=suite_path,
            suite=suite,
            cases=cases,
            repetitions=args.repetitions,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            timeout_seconds=args.timeout_seconds,
            seed=args.seed,
        )
    except ChallengeRunnerError as exc:
        parser.error(str(exc))
    if not args.execute:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    if args.max_model_runs is None:
        parser.error("--execute requires --max-model-runs")
    if args.max_model_runs < plan["model_run_count"]:
        parser.error(
            "planned model runs exceed --max-model-runs "
            f"({plan['model_run_count']} > {args.max_model_runs})"
        )
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_root = args.output_dir.resolve() / run_id
    run_root.mkdir(parents=True)
    results = [
        _run_case(
            case,
            repetition=repetition,
            run_root=run_root,
            codex_command=args.codex_command,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            timeout_seconds=args.timeout_seconds,
        )
        for case in cases
        for repetition in range(1, args.repetitions + 1)
    ]
    summary = {
        **plan,
        "mode": "execute",
        "execution_requested": True,
        "max_model_runs": args.max_model_runs,
        "run_id": run_id,
        "completed_at": _timestamp(),
        "results": results,
    }
    (run_root / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if all(result["exit_code"] == 0 for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
