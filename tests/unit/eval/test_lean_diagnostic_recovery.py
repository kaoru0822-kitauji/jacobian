from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from benchmarks.tooling.lean_diagnostic_recovery import (
    classify_recovery,
    compare_reports,
    digest_suite,
    load_suite,
    summarize_runs,
)

ROOT = Path(__file__).resolve().parents[3]
SUITE = ROOT / "benchmarks/config/lean-diagnostic-recovery-v1.json"
BASE_REVISION = "1" * 40
CANDIDATE_REVISION = "2" * 40


def _surface(seed: str) -> dict[str, object]:
    return {
        "server": {"name": "jacobian", "version": "0.11.0"},
        "catalog": {
            "catalog_digest": "sha256:" + seed * 64,
            "policy_profile": "default",
            "policy_digest": "sha256:" + "9" * 64,
        },
        "surface_digest": "sha256:" + seed * 64,
    }


def _comparison_report(
    condition: str,
    *,
    surface_seed: str | None = None,
) -> dict[str, object]:
    control = condition == "control"
    return {
        "schema_version": "1",
        "evidence_class": "public-host-local-lean-recovery-observation",
        "causal_claim_authorized": False,
        "suite_id": "lean-diagnostic-recovery-v1",
        "suite_digest": "sha256:" + "a" * 64,
        "source_base_revision": BASE_REVISION,
        "source_candidate_revision": CANDIDATE_REVISION,
        "deployed_revision": BASE_REVISION if control else CANDIDATE_REVISION,
        "condition": condition,
        "model": "test-model",
        "reasoning_effort": "high",
        "tool_mode": "direct",
        "repetitions": 1,
        "timeout_seconds": 300.0,
        "codex_version": "codex-test",
        "skill_digest": None,
        "selected_case_ids": ["core-check-type-mismatch"],
        "surface": _surface(surface_seed or ("b" if control else "c")),
        "summary": {
            "run_count": 1,
            "repair_success_rate": 0.0,
            "repeated_error_count": 1,
            "math_run_call_count": 3,
            "input_tokens": 130,
            "output_tokens": 30,
            "elapsed_seconds": 5.0,
        },
    }


def test_recovery_suite_freezes_control_treatment_and_injected_cases() -> None:
    suite = load_suite(SUITE)

    assert {condition.id for condition in suite.conditions} == {
        "control",
        "enriched-diagnostics",
    }
    assert len(suite.cases) == 3
    assert any("MATHLIB" in case.prompt for case in suite.cases)
    assert suite.causal_claim_authorized is False


def test_recovery_suite_bytes_have_a_stable_evaluation_identity() -> None:
    expected = "sha256:" + hashlib.sha256(SUITE.read_bytes()).hexdigest()

    assert digest_suite(SUITE) == expected


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
    control = _comparison_report("control")
    treatment = _comparison_report("enriched-diagnostics")

    compared = compare_reports(
        {**control, "summary": control_summary},
        {**treatment, "summary": treatment_summary},
    )

    assert compared["deltas"]["repair_success_rate"] == 1.0
    assert compared["deltas"]["repeated_error_count"] == -1
    assert compared["causal_claim_authorized"] is False
    assert (
        compared["condition_bindings"]["control"]["deployed_revision"] == BASE_REVISION
    )
    assert (
        compared["condition_bindings"]["enriched-diagnostics"]["deployed_revision"]
        == CANDIDATE_REVISION
    )


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
    control = _comparison_report("control")
    treatment = _comparison_report("enriched-diagnostics")
    with pytest.raises(ValueError, match="model"):
        compare_reports(control, {**treatment, "model": "second"})


@pytest.mark.parametrize(
    ("field", "changed", "message"),
    (
        ("timeout_seconds", 301.0, "timeout_seconds"),
        ("selected_case_ids", ["proof-edit-type-mismatch"], "selected_case_ids"),
        ("source_base_revision", "3" * 40, "source_base_revision"),
        ("source_candidate_revision", "4" * 40, "source_candidate_revision"),
    ),
)
def test_recovery_comparison_rejects_run_invariant_drift(
    field: str,
    changed: object,
    message: str,
) -> None:
    control = _comparison_report("control")
    treatment = _comparison_report("enriched-diagnostics")

    with pytest.raises(ValueError, match=message):
        compare_reports(control, {**treatment, field: changed})


def test_recovery_comparison_rejects_mislabeled_conditions() -> None:
    control = _comparison_report("control")

    with pytest.raises(ValueError, match="enriched-diagnostics condition"):
        compare_reports(control, {**control, "deployed_revision": CANDIDATE_REVISION})


def test_recovery_comparison_binds_each_deployment_to_its_source_revision() -> None:
    control = _comparison_report("control")
    treatment = _comparison_report("enriched-diagnostics")

    with pytest.raises(ValueError, match="source_base_revision"):
        compare_reports({**control, "deployed_revision": "3" * 40}, treatment)


def test_recovery_comparison_rejects_the_same_observed_server_surface() -> None:
    control = _comparison_report("control", surface_seed="b")
    treatment = _comparison_report("enriched-diagnostics", surface_seed="b")

    with pytest.raises(ValueError, match="same MCP surface"):
        compare_reports(control, treatment)
