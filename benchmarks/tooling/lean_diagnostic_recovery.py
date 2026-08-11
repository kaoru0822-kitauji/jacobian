"""Operator-run Codex observation for Lean diagnostic-guided recovery."""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from benchmarks.tooling.codex_visibility import (
    _CODEX_ENVIRONMENT,
    ToolMode,
    _codex_arguments,
    _command_version,
    _copy_skill,
    _sha256_bytes,
    _validate_mcp_url,
    inspect_surface,
)
from benchmarks.tooling.command_runner import (
    ToolCommandStatus,
    operator_environment,
    run_operator_command,
)
from jacobian.eval.telemetry import parse_agent_transcript

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SUITE = _ROOT / "benchmarks/config/lean-diagnostic-recovery-v1.json"


class RecoveryCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Literal["control", "enriched-diagnostics"]
    description: str = Field(min_length=1)


class RecoveryCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    injected_capability_id: str = Field(min_length=1)
    injected_payload: dict[str, Any]
    expected_diagnostic_codes: tuple[str, ...] = Field(min_length=1)
    terminal_capability_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_stable_unique_codes(self) -> Self:
        if len(set(self.expected_diagnostic_codes)) != len(
            self.expected_diagnostic_codes
        ):
            raise ValueError("expected diagnostic codes must be unique")
        if any(
            not code.startswith("LEAN_") or not code.replace("_", "").isalnum()
            for code in self.expected_diagnostic_codes
        ):
            raise ValueError("expected diagnostic codes must be stable Lean codes")
        return self


class RecoveryExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repetitions_per_case: int = Field(ge=1, le=20)
    timeout_seconds_per_rollout: float = Field(gt=0)
    wrong_answer_retries: Literal[0]
    web_search: Literal["disabled"]


class RecoverySuite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"]
    suite_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    evidence_class: str = Field(min_length=1)
    causal_claim_authorized: Literal[False]
    source_base_revision: str = Field(pattern=r"^[0-9a-f]{12,40}$")
    conditions: tuple[RecoveryCondition, RecoveryCondition]
    cases: tuple[RecoveryCase, ...] = Field(min_length=1)
    execution: RecoveryExecution
    primary_metric: Literal["repair_success_rate"]
    secondary_metrics: tuple[str, ...] = Field(min_length=1)
    invariants: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_cases_and_conditions(self) -> Self:
        if {condition.id for condition in self.conditions} != {
            "control",
            "enriched-diagnostics",
        }:
            raise ValueError("recovery study requires control and enriched conditions")
        case_ids = tuple(case.case_id for case in self.cases)
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("recovery case IDs must be unique")
        return self


def load_suite(path: Path) -> RecoverySuite:
    return RecoverySuite.model_validate_json(path.read_text(encoding="utf-8"))


def digest_suite(path: Path) -> str:
    """Bind an observation to the exact version-controlled suite bytes."""

    return _sha256_bytes(path.read_bytes())


def _diagnostic_codes(invocation: Mapping[str, Any]) -> tuple[str, ...]:
    output = invocation.get("output")
    diagnostics = output.get("diagnostics") if isinstance(output, Mapping) else None
    if not isinstance(diagnostics, list):
        return ()
    return tuple(
        diagnostic["code"]
        for diagnostic in diagnostics
        if isinstance(diagnostic, Mapping) and isinstance(diagnostic.get("code"), str)
    )


def _invocation_rejected(invocation: Mapping[str, Any]) -> bool:
    output = invocation.get("output")
    if not isinstance(output, Mapping):
        return False
    input_validation = output.get("input")
    return bool(
        output.get("accepted") is False
        or output.get("conclusion") == "UNKNOWN"
        or (
            isinstance(input_validation, Mapping)
            and input_validation.get("status") == "REJECTED"
        )
    )


def _terminal_accepted(invocation: Mapping[str, Any]) -> bool:
    output = invocation.get("output")
    assurance = invocation.get("assurance")
    return bool(
        isinstance(output, Mapping)
        and (output.get("accepted") is True or output.get("conclusion") == "TRUE")
        and isinstance(assurance, Mapping)
        and assurance.get("level") == "VERIFIED"
        and isinstance(assurance.get("verification_record_uri"), str)
    )


def classify_recovery(
    case: RecoveryCase,
    telemetry: Mapping[str, Any],
) -> dict[str, Any]:
    invocations = tuple(
        invocation
        for invocation in telemetry.get("capability_invocations", [])
        if isinstance(invocation, Mapping)
    )
    injected = tuple(
        invocation
        for invocation in invocations
        if invocation.get("capability_id") == case.injected_capability_id
    )
    first_invocation = invocations[0] if invocations else None
    injection_payload_exact = bool(
        isinstance(first_invocation, Mapping)
        and first_invocation.get("capability_id") == case.injected_capability_id
        and first_invocation.get("input") == case.injected_payload
    )
    terminal = tuple(
        invocation
        for invocation in (invocations[1:] if injection_payload_exact else ())
        if invocation.get("capability_id") == case.terminal_capability_id
    )
    first_codes = (
        _diagnostic_codes(first_invocation)
        if injection_payload_exact and first_invocation is not None
        else ()
    )
    expected_codes = set(case.expected_diagnostic_codes)
    rejection_fingerprints = [
        (str(invocation.get("capability_id")), _diagnostic_codes(invocation))
        for invocation in invocations
        if _invocation_rejected(invocation)
    ]
    repeated_errors = sum(
        fingerprint in rejection_fingerprints[:index]
        for index, fingerprint in enumerate(rejection_fingerprints)
    )
    usage = telemetry.get("usage")
    return {
        "injection_attempted": bool(injected),
        "injection_payload_exact": injection_payload_exact,
        "injection_rejected": bool(
            injection_payload_exact
            and first_invocation is not None
            and _invocation_rejected(first_invocation)
        ),
        "observed_diagnostic_codes": list(first_codes),
        "enriched_diagnostic_observed": bool(expected_codes & set(first_codes)),
        "repair_success": bool(
            injection_payload_exact
            and first_invocation is not None
            and _invocation_rejected(first_invocation)
            and any(_terminal_accepted(invocation) for invocation in terminal)
        ),
        "repeated_error_count": repeated_errors,
        "repeated_mcp_call_count": int(telemetry.get("repeated_mcp_call_count", 0)),
        "math_run_call_count": sum(
            call == "math.run" for call in telemetry.get("mcp_calls", [])
        ),
        "tool_error_count": int(telemetry.get("tool_error_count", 0)),
        "tokens": usage if isinstance(usage, Mapping) else None,
    }


def _run_case(
    *,
    case: RecoveryCase,
    repetition: int,
    workspace: Path,
    output: Path,
    model: str,
    reasoning_effort: str,
    mcp_url: str,
    timeout_seconds: float,
    tool_mode: ToolMode,
) -> dict[str, Any]:
    stem = f"{case.case_id}-r{repetition:02d}"
    transcript_path = output / f"{stem}.jsonl"
    stderr_path = output / f"{stem}.stderr"
    started = time.monotonic()
    result = run_operator_command(
        "codex",
        _codex_arguments(
            workspace=workspace,
            model=model,
            reasoning_effort=reasoning_effort,
            mcp_url=mcp_url,
            prompt=case.prompt,
            tool_mode=tool_mode,
        ),
        cwd=workspace,
        timeout_seconds=timeout_seconds,
        stdout_limit_bytes=16 * 1024 * 1024,
        stderr_limit_bytes=2 * 1024 * 1024,
        environment=operator_environment(include=_CODEX_ENVIRONMENT),
    )
    transcript_path.write_bytes(result.stdout)
    stderr_path.write_bytes(result.stderr)
    telemetry = parse_agent_transcript(transcript_path)
    classified = classify_recovery(case, telemetry)
    completed = result.status is ToolCommandStatus.EXITED and result.exit_code == 0
    return {
        "case_id": case.case_id,
        "repetition": repetition,
        "command": {
            "status": result.status,
            "exit_code": result.exit_code,
            "elapsed_seconds": round(time.monotonic() - started, 6),
        },
        "metrics": {
            **classified,
            "repair_success": completed and classified["repair_success"],
        },
        "artifacts": {
            "transcript": transcript_path.name,
            "transcript_sha256": _sha256_bytes(result.stdout),
            "stderr": stderr_path.name,
            "stderr_sha256": _sha256_bytes(result.stderr),
        },
    }


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    run_count = len(runs)
    return {
        "run_count": run_count,
        "repair_success_count": sum(run["metrics"]["repair_success"] for run in runs),
        "repair_success_rate": (
            sum(run["metrics"]["repair_success"] for run in runs) / run_count
            if run_count
            else 0.0
        ),
        "enriched_diagnostic_observation_count": sum(
            run["metrics"]["enriched_diagnostic_observed"] for run in runs
        ),
        "injection_protocol_compliance_count": sum(
            run["metrics"]["injection_payload_exact"]
            and run["metrics"]["injection_rejected"]
            for run in runs
        ),
        "repeated_error_count": sum(
            run["metrics"]["repeated_error_count"] for run in runs
        ),
        "math_run_call_count": sum(
            run["metrics"]["math_run_call_count"] for run in runs
        ),
        "input_tokens": sum(
            (run["metrics"]["tokens"] or {}).get("input_tokens", 0) for run in runs
        ),
        "output_tokens": sum(
            (run["metrics"]["tokens"] or {}).get("output_tokens", 0) for run in runs
        ),
        "elapsed_seconds": round(
            sum(run["command"]["elapsed_seconds"] for run in runs), 6
        ),
    }


def compare_reports(
    control: Mapping[str, Any],
    treatment: Mapping[str, Any],
) -> dict[str, Any]:
    for field in (
        "suite_digest",
        "model",
        "reasoning_effort",
        "tool_mode",
        "repetitions",
    ):
        if control.get(field) != treatment.get(field):
            raise ValueError(f"recovery comparison invariant differs: {field}")
    control_summary = control.get("summary")
    treatment_summary = treatment.get("summary")
    if not isinstance(control_summary, Mapping) or not isinstance(
        treatment_summary, Mapping
    ):
        raise ValueError("recovery reports require summaries")
    return {
        "schema_version": "1",
        "causal_claim_authorized": False,
        "suite_digest": control["suite_digest"],
        "control_condition": control.get("condition"),
        "treatment_condition": treatment.get("condition"),
        "deltas": {
            metric: treatment_summary[metric] - control_summary[metric]
            for metric in (
                "repair_success_rate",
                "repeated_error_count",
                "math_run_call_count",
                "input_tokens",
                "output_tokens",
                "elapsed_seconds",
            )
        },
        "interpretation": (
            "Descriptive public observation only; task identity and run invariants "
            "match, but this report does not authorize a causal claim."
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=_DEFAULT_SUITE)
    parser.add_argument("--condition", choices=("control", "enriched-diagnostics"))
    parser.add_argument("--mcp-url")
    parser.add_argument("--model")
    parser.add_argument("--reasoning-effort", default="high")
    parser.add_argument(
        "--tool-mode", type=ToolMode, choices=tuple(ToolMode), default=ToolMode.DIRECT
    )
    parser.add_argument("--repetitions", type=int)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--skill", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--compare", nargs=2, type=Path, metavar=("CONTROL", "TREATMENT")
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.compare:
        control = json.loads(args.compare[0].read_text(encoding="utf-8"))
        treatment = json.loads(args.compare[1].read_text(encoding="utf-8"))
        print(json.dumps(compare_reports(control, treatment), indent=2, sort_keys=True))
        return
    if not args.execute:
        raise SystemExit("refusing model execution without --execute")
    if not args.condition or not args.mcp_url or not args.model or args.output is None:
        raise SystemExit(
            "run mode requires --condition, --mcp-url, --model, and --output"
        )
    _validate_mcp_url(args.mcp_url)
    suite_path = args.suite.resolve(strict=True)
    suite = load_suite(suite_path)
    suite_digest = digest_suite(suite_path)
    repetitions = args.repetitions or suite.execution.repetitions_per_case
    timeout = args.timeout_seconds or suite.execution.timeout_seconds_per_rollout
    if not 1 <= repetitions <= 20 or timeout <= 0:
        raise SystemExit("invalid repetition or timeout bound")
    available = {case.case_id for case in suite.cases}
    unknown = sorted(set(args.case) - available)
    if unknown:
        raise SystemExit(f"unknown case IDs: {unknown}")
    selected = tuple(
        case for case in suite.cases if not args.case or case.case_id in args.case
    )
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"output directory already exists: {output}")
    surface = asyncio.run(inspect_surface(args.mcp_url, timeout))
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="jacobian-lean-recovery-") as raw:
        workspace = Path(raw)
        skill_digest = (
            _copy_skill(args.skill.resolve(strict=True), workspace)
            if args.skill is not None
            else None
        )
        codex_version = _command_version(workspace)
        runs = [
            _run_case(
                case=case,
                repetition=repetition,
                workspace=workspace,
                output=output,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                mcp_url=args.mcp_url,
                timeout_seconds=timeout,
                tool_mode=args.tool_mode,
            )
            for case in selected
            for repetition in range(1, repetitions + 1)
        ]
    report = {
        "schema_version": "1",
        "evidence_class": suite.evidence_class,
        "causal_claim_authorized": False,
        "suite_id": suite.suite_id,
        "suite_digest": suite_digest,
        "condition": args.condition,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "tool_mode": args.tool_mode,
        "repetitions": repetitions,
        "timeout_seconds": timeout,
        "codex_version": codex_version,
        "skill_digest": skill_digest,
        "surface": surface,
        "selected_case_ids": [case.case_id for case in selected],
        "runs": runs,
        "summary": summarize_runs(runs),
    }
    (output / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
