from __future__ import annotations

import json
import runpy
from pathlib import Path
from typing import Any, cast

from jacobian.contracts.capabilities import CapabilityMode, CapabilityRequest
from jacobian.kernel import JacobianKernel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = runpy.run_path(str(PROJECT_ROOT / "benchmarks" / "agent_ab.py"))


def _report(
    *,
    assurance: str,
    verification_record_uri: str | None,
) -> dict[str, Any]:
    return {
        "case_id": "ERDOS-STRAUS-AB-001",
        "conclusion": "TRUE",
        "checked_count": 119,
        "first_failure": None,
        "assurance": assurance,
        "verification_record_uri": verification_record_uri,
        "limitations": ["finite interval only"],
        "feedback": {
            "reasoning_focus": ["bounded interpretation"],
            "infrastructure_work": [],
            "tooling_gaps": [],
        },
    }


def test_ab_transcript_parser_separates_mcp_and_shell_calls(tmp_path: Path) -> None:
    parse_transcript = cast(Any, BENCHMARK["parse_transcript"])
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\n".join(
            json.dumps(event)
            for event in (
                {
                    "type": "item.completed",
                    "item": {
                        "type": "command_execution",
                        "command": "python solve.py",
                    },
                },
                {
                    "type": "item.completed",
                    "item": {
                        "type": "mcp_tool_call",
                        "tool": "capability.invoke",
                    },
                },
                {
                    "type": "turn.completed",
                    "usage": {"input_tokens": 12, "output_tokens": 3},
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )

    telemetry = parse_transcript(transcript)

    assert telemetry == {
        "mcp_calls": ["capability.invoke"],
        "shell_calls": ["python solve.py"],
        "usage": {"input_tokens": 12, "output_tokens": 3},
    }


def test_ab_scorer_accepts_control_and_durable_treatment(tmp_path: Path) -> None:
    load_cases = cast(Any, BENCHMARK["load_cases"])
    score_report = cast(Any, BENCHMARK["score_report"])
    case = load_cases(["ERDOS-STRAUS-AB-001"])[0]

    control = score_report(
        case,
        _report(assurance="SELF_CHECKED", verification_record_uri=None),
        condition="control",
        state_dir=tmp_path / "unused",
        mcp_calls=[],
    )
    assert control["passed"] is True

    state_dir = tmp_path / "treatment"
    kernel = JacobianKernel(state_dir, install_references=True)
    result = kernel.capabilities.invoke(
        CapabilityRequest(
            capability_id="reference.solve",
            mode=CapabilityMode.VERIFY,
            input={
                "reference_name": "erdos_straus",
                "predicate": {
                    "name": "erdos_straus_range",
                    "parameters": {"lower_bound": 2, "upper_bound": 120},
                },
                "candidate": {"lower_bound": 2, "upper_bound": 120},
                "witness_role": "SUPPORTS_CLAIM",
                "evaluation_wall_seconds": 30,
                "witness_wall_seconds": 30,
            },
        )
    )
    record_uri = result.assurance.verification_record_uri
    assert record_uri is not None
    treatment = score_report(
        case,
        _report(assurance="VERIFIED", verification_record_uri=record_uri),
        condition="treatment",
        state_dir=state_dir,
        mcp_calls=["capability.invoke"],
    )
    assert treatment["passed"] is True


def test_ab_summary_reports_paired_deltas() -> None:
    summarize_pairs = cast(Any, BENCHMARK["summarize_pairs"])
    results = [
        {
            "case_id": "C",
            "repetition": 1,
            "condition": "control",
            "score": {"passed": True},
            "elapsed_seconds": 10,
            "usage": {"input_tokens": 100, "output_tokens": 20},
            "shell_call_count": 2,
            "mcp_call_count": 0,
        },
        {
            "case_id": "C",
            "repetition": 1,
            "condition": "treatment",
            "score": {"passed": True},
            "elapsed_seconds": 6,
            "usage": {"input_tokens": 60, "output_tokens": 10},
            "shell_call_count": 0,
            "mcp_call_count": 1,
        },
    ]

    summary = summarize_pairs(results)

    assert summary["pair_count"] == 1
    assert summary["pairs"][0]["input_token_delta"] == -40
    assert summary["pairs"][0]["elapsed_delta_seconds"] == -4
