from __future__ import annotations

from pathlib import Path

import pytest
from benchmarks.tooling.lean_diagnostic_recovery import (
    classify_recovery,
    compare_reports,
    load_suite,
    summarize_runs,
)

ROOT = Path(__file__).resolve().parents[3]
SUITE = ROOT / "benchmarks/config/lean-diagnostic-recovery-v1.json"


def test_recovery_suite_freezes_control_treatment_and_injected_cases() -> None:
    suite = load_suite(SUITE)

    assert {condition.id for condition in suite.conditions} == {
        "control",
        "enriched-diagnostics",
    }
    assert len(suite.cases) == 3
    assert any("MATHLIB" in case.prompt for case in suite.cases)
    assert suite.causal_claim_authorized is False


def test_recovery_classification_separates_diagnostic_from_terminal_success() -> None:
    case = load_suite(SUITE).cases[0]
    telemetry = {
        "mcp_calls": ["math.run", "math.run"],
        "repeated_mcp_call_count": 0,
        "tool_error_count": 0,
        "usage": {"input_tokens": 100, "output_tokens": 20},
        "capability_invocations": [
            {
                "capability_id": "lean.check",
                "input": case.injected_payload,
                "output": {
                    "conclusion": "UNKNOWN",
                    "diagnostics": [{"code": "LEAN_TYPE_MISMATCH"}],
                },
                "assurance": {"level": "HEURISTIC"},
            },
            {
                "capability_id": "lean.check",
                "output": {"conclusion": "TRUE", "diagnostics": []},
                "assurance": {
                    "level": "VERIFIED",
                    "verification_record_uri": "artifact://sha256/" + "a" * 64,
                },
            },
        ],
    }

    result = classify_recovery(case, telemetry)

    assert result["injection_rejected"] is True
    assert result["injection_payload_exact"] is True
    assert result["enriched_diagnostic_observed"] is True
    assert result["repair_success"] is True
    assert result["math_run_call_count"] == 2
    assert result["repeated_error_count"] == 0


def test_recovery_summary_and_comparison_keep_efficiency_metrics_separate() -> None:
    runs = [
        {
            "metrics": {
                "repair_success": True,
                "enriched_diagnostic_observed": True,
                "injection_payload_exact": True,
                "injection_rejected": True,
                "repeated_error_count": 0,
                "math_run_call_count": 2,
                "tokens": {"input_tokens": 100, "output_tokens": 20},
            },
            "command": {"elapsed_seconds": 3.5},
        }
    ]
    treatment_summary = summarize_runs(runs)
    control_summary = {
        **treatment_summary,
        "repair_success_rate": 0.0,
        "repeated_error_count": 1,
        "math_run_call_count": 3,
        "input_tokens": 130,
        "output_tokens": 30,
        "elapsed_seconds": 5.0,
    }
    common = {
        "suite_digest": "sha256:" + "a" * 64,
        "model": "test-model",
        "reasoning_effort": "high",
        "tool_mode": "direct",
        "repetitions": 1,
    }

    compared = compare_reports(
        {**common, "condition": "control", "summary": control_summary},
        {
            **common,
            "condition": "enriched-diagnostics",
            "summary": treatment_summary,
        },
    )

    assert compared["deltas"]["repair_success_rate"] == 1.0
    assert compared["deltas"]["repeated_error_count"] == -1
    assert compared["causal_claim_authorized"] is False


def test_recovery_does_not_count_a_repaired_call_before_exact_injection() -> None:
    case = load_suite(SUITE).cases[0]
    telemetry = {
        "capability_invocations": [
            {
                "capability_id": "lean.check",
                "input": {"statement": "True", "proof": "by trivial"},
                "output": {"conclusion": "TRUE"},
                "assurance": {
                    "level": "VERIFIED",
                    "verification_record_uri": "artifact://sha256/" + "a" * 64,
                },
            },
            {
                "capability_id": "lean.check",
                "input": case.injected_payload,
                "output": {
                    "conclusion": "UNKNOWN",
                    "diagnostics": [{"code": "LEAN_TYPE_MISMATCH"}],
                },
                "assurance": {"level": "HEURISTIC"},
            },
        ]
    }

    result = classify_recovery(case, telemetry)

    assert result["injection_attempted"] is True
    assert result["injection_payload_exact"] is False
    assert result["repair_success"] is False


def test_recovery_comparison_rejects_model_drift() -> None:
    base = {
        "suite_digest": "sha256:" + "a" * 64,
        "model": "first",
        "reasoning_effort": "high",
        "tool_mode": "direct",
        "repetitions": 1,
        "summary": {},
    }
    with pytest.raises(ValueError, match="model"):
        compare_reports(base, {**base, "model": "second"})
